#!/usr/bin/env python3
"""Check portable skill metadata, resources, and local documentation links."""

from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path = ROOT) -> list[str]:
    skill_root = root / "skills" / "dev-artifact-cleanup"
    errors = []
    source = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    parts = source.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        return ["SKILL.md must start with YAML frontmatter"]
    metadata = yaml.safe_load(parts[1])
    if not isinstance(metadata, dict):
        return ["SKILL.md frontmatter must be a mapping"]
    if metadata.get("name") != skill_root.name:
        errors.append("Skill name must match the canonical directory")
    description = metadata.get("description")
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
        errors.append("Description must be a nonempty string of at most 1024 characters")
    compatibility = metadata.get("compatibility")
    if not isinstance(compatibility, str) or not 1 <= len(compatibility) <= 500:
        errors.append("Compatibility must describe requirements in at most 500 characters")
    if metadata.get("license") != "MIT":
        errors.append("Portable skill must declare its MIT license")
    details = metadata.get("metadata", {})
    if not isinstance(details, dict) or not all(isinstance(v, str) for v in details.values()):
        return errors + ["Metadata values must be strings"]
    version = details.get("version", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", version):
        errors.append("metadata.version must be a quoted semantic version")
    if f"## Version\n\n{version}." not in source:
        errors.append("Version section must match metadata.version")
    runtimes = {value.strip() for value in details.get("supported-runtimes", "").split(",")}
    if not {"claude-code", "github-copilot", "cursor", "codex", "skills.sh"} <= runtimes:
        errors.append("Supported runtimes must identify the documented installation targets")
    common_fields = {"name", "description", "license", "compatibility", "metadata"}
    if set(metadata) - common_fields:
        errors.append("Shared frontmatter must not require host-specific extensions")
    if (root / "LICENSE").read_bytes() != (skill_root / "LICENSE.txt").read_bytes():
        errors.append("Bundled LICENSE.txt must match the repository LICENSE")

    for document in root.rglob("*.md"):
        if any(part.startswith(".") and part not in {".github"} for part in document.relative_to(root).parts):
            continue
        text = document.read_text(encoding="utf-8")
        # Ignore examples in fenced code blocks; validate actual Markdown links.
        text = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.M | re.S)
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            link = target.strip().strip("<>")
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (document.parent / unquote(parsed.path)).resolve()
            if not resolved.exists():
                errors.append(f"{document.relative_to(root)}: missing local target {link}")
            if skill_root in document.parents and skill_root.resolve() not in (resolved, *resolved.parents):
                errors.append(f"{document.relative_to(root)}: link escapes installed package: {link}")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)
    print("Portable metadata, bundled license, version, and local links valid")
