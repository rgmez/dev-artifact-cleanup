#!/usr/bin/env python3
"""Verify real skills CLI discovery and installation in a temporary project."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SKILL = "dev-artifact-cleanup"
AGENTS = {
    "claude-code": "Claude Code",
    "github-copilot": "GitHub Copilot",
    "cursor": "Cursor",
    "codex": "Codex",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT), help="Local repository or GitHub owner/repo")
    args = parser.parse_args()
    env = dict(os.environ, DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", CI="1", NO_COLOR="1")
    cli = ["npx", "--yes", "skills@1.7.4", "add", args.source]
    source = ROOT / "skills" / SKILL

    with tempfile.TemporaryDirectory(prefix="dev-artifact-cleanup-install-") as temporary:
        project = Path(temporary)
        subprocess.run(["git", "init", "--quiet", str(project)], check=True, env=env)
        discovery = subprocess.run(
            cli + ["--list"], cwd=project, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, check=True,
        )
        if SKILL not in discovery.stdout:
            raise RuntimeError("CLI did not discover dev-artifact-cleanup")
        subprocess.run(
            cli + ["--skill", SKILL, "--agent", *AGENTS, "--copy", "--yes"],
            cwd=project, env=env, timeout=120, check=True,
        )
        # Verify both the public agent IDs and the full resource payload installed.
        listing = subprocess.run(
            ["npx", "--yes", "skills@1.7.4", "list", "--json"],
            cwd=project, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=60, check=True,
        )
        records = [entry for entry in json.loads(listing.stdout) if entry["name"] == SKILL]
        if len(records) != 1:
            raise RuntimeError("CLI list must report exactly one installed cleanup skill")
        for agent, display_name in AGENTS.items():
            if display_name not in records[0].get("agents", []):
                raise RuntimeError(f"CLI list did not confirm installation for {agent}")
        installed = sorted(project.rglob(f"{SKILL}/SKILL.md"))
        if not installed:
            raise RuntimeError("No installed SKILL.md found")
        for entry in installed:
            for resource in source.rglob("*"):
                if resource.is_file():
                    copy = entry.parent / resource.relative_to(source)
                    if not copy.is_file() or copy.read_bytes() != resource.read_bytes():
                        raise RuntimeError(f"Resource missing or modified: {copy.relative_to(project)}")
        print(f"Discovery and complete payload verified for {', '.join(AGENTS)}")
        print("Temporary project removed; no global installation or agent settings changed")


if __name__ == "__main__":
    main()
