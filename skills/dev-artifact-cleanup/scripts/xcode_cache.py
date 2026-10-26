#!/usr/bin/env python3
"""Audit and explicitly remove a small set of dedicated Xcode cache directories."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
import uuid


ADAPTER = "xcode-dedicated-cache-v1"
CACHES = ("Index.noindex", "CompilationCache.noindex", "ModuleCache.noindex", "SDKStatCaches.noindex")
PROTECTED_SUFFIXES = {
    ".swift", ".m", ".mm", ".h", ".c", ".cpp", ".md", ".txt", ".text",
    ".json", ".plist", ".yaml", ".yml", ".toml", ".sh", ".py", ".log",
    ".db", ".sqlite", ".csv", ".pdf", ".png", ".jpg", ".pem", ".p12",
    ".mobileprovision", ".xcresult", ".xcarchive", ".dsym",
    ".xcconfig", ".pbxproj", ".storyboard", ".xib", ".entitlements", ".strings", ".stringsdict", ".xcassets", ".lproj",
    ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".kt", ".kts", ".java", ".rb", ".rs", ".go", ".sql",
    ".docx", ".xlsx", ".pptx", ".jpeg", ".webp", ".heic", ".svg", ".key", ".p8", ".cer", ".crt",
}
MAX_ENTRIES = 100_000


class AdapterError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git(repository, *arguments, input_text=None):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    command = ["git", "-c", f"core.hooksPath={os.devnull}", "-c", "core.fsmonitor=false", "-C", str(repository), *arguments]
    try:
        return subprocess.run(command, text=True, input=input_text, capture_output=True, env=environment, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AdapterError(f"Git inspection unavailable: {error}") from error


def check_activity():
    """Conservatively refuse while any Xcode/compiler/indexing process is visible."""
    try:
        result = subprocess.run(["ps", "-axo", "comm="], text=True, capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AdapterError("Process activity could not be checked") from error
    if result.returncode or not result.stdout.strip():
        raise AdapterError("Process activity could not be checked")
    busy = {"Xcode", "xcodebuild", "xcbuild", "XCBBuildService", "swift-frontend", "swiftc", "swift-build", "clang", "clang++", "sourcekit-lsp", "SourceKitService", "xctest", "Simulator", "ibtoold", "actool", "assetcatalogd"}
    if any(Path(line.strip()).name in busy for line in result.stdout.splitlines()):
        raise AdapterError("Xcode, compilation or indexing is active; retry after it stops")


def canonical(path):
    path = Path(path)
    if not path.is_absolute() or path != path.resolve() or ".." in path.parts:
        raise AdapterError("Paths must be absolute, physical paths without symbolic-link components")
    return path


@contextmanager
def directory(path):
    """Open each path component relative to its verified parent without following links."""
    path = canonical(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def identity(info):
    return [info.st_dev, info.st_ino]


def read_at(parent, name, limit=2_000_000):
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise AdapterError("Metadata must be a bounded regular file")
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit or identity(info) != identity(before):
            raise AdapterError("Metadata must be a bounded regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read(limit + 1)
    finally:
        os.close(descriptor)


def inspect_context(repository, derived_data, workspace):
    repository, derived_data, workspace = map(canonical, (repository, derived_data, workspace))
    if repository not in derived_data.parents or repository not in workspace.parents:
        raise AdapterError("DerivedData and workspace must be inside the specified repository")
    if ".git" in derived_data.relative_to(repository).parts or workspace.suffix not in {".xcodeproj", ".xcworkspace"}:
        raise AdapterError("Unsupported workspace or protected Git metadata path")
    with directory(repository), directory(workspace), directory(derived_data) as descriptor:
        top = git(repository, "rev-parse", "--show-toplevel")
        trees = git(repository, "worktree", "list", "--porcelain")
        primary = next((line[9:] for line in trees.stdout.splitlines() if line.startswith("worktree ")), None)
        if top.returncode or trees.returncode or top.stdout.strip() != str(repository) or primary != str(repository):
            raise AdapterError("Only the verified primary Git checkout is supported")
        contents = read_at(descriptor, "info.plist")
        try:
            owner = plistlib.loads(contents).get("WorkspacePath")
        except (ValueError, AttributeError, plistlib.InvalidFileException) as error:
            raise AdapterError("Invalid DerivedData workspace metadata") from error
        if not isinstance(owner, str) or Path(owner) != workspace or Path(owner).resolve() != workspace:
            raise AdapterError("DerivedData WorkspacePath does not match the requested workspace")
        for ancestor in (derived_data, *derived_data.parents):
            with directory(ancestor) as ancestor_fd:
                info = os.fstat(ancestor_fd)
                if info.st_uid != os.getuid() or info.st_mode & 0o022:
                    raise AdapterError("Repository-to-DerivedData path must be owned and not shared-writable")
            if ancestor == repository:
                break
        return repository, derived_data, workspace, {
            "derivedDataIdentity": identity(os.fstat(descriptor)),
            "infoPlistSha256": hashlib.sha256(contents).hexdigest(),
        }


def content_signature(cache_name, relative, is_directory):
    """Recognize one observed IndexStore layout; unknown layouts fail closed."""
    parts = Path(relative).parts
    if cache_name != "Index.noindex":
        raise AdapterError("No validated content profile for this nonempty cache")
    containers = {("DataStore",), ("DataStore", "v5"), ("DataStore", "v5", "records"), ("DataStore", "v5", "units")}
    if is_directory:
        if parts in containers or (len(parts) == 4 and parts[:3] == ("DataStore", "v5", "records") and re.fullmatch(r"[A-Z0-9]{2}", parts[3])):
            return None
    elif ((len(parts) == 5 and parts[:3] == ("DataStore", "v5", "records") and re.fullmatch(r"[A-Z0-9]{2}", parts[3]))
          or (len(parts) == 4 and parts[:3] == ("DataStore", "v5", "units"))):
        if re.fullmatch(r"[^/]+-[A-Z0-9]{8,32}", parts[-1]):
            return b"IDXR" if parts[2] == "records" else b"IDXU"
    raise AdapterError("Unrecognized generated-content layout: " + relative)


def check_content(descriptor, name, entry, signature):
    """Bounded header recognition, not a full IndexStore parser or origin proof."""
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    try:
        current = os.fstat(child)
        if not stat.S_ISREG(current.st_mode) or identity(current) != identity(entry):
            raise AdapterError("Cache entry changed before content inspection")
        header = os.read(child, 12)
        words = int.from_bytes(header[8:12], "little")
        if (len(header) != 12 or header[:8] != signature + b"\x01\x08\x00\x00"
                or current.st_size < 16 or current.st_size % 4 or not 0 < words <= (current.st_size - 12) // 4):
            raise AdapterError("Unrecognized or truncated generated-content signature: " + name)
        after = os.fstat(child)
        def metadata(info):
            return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if metadata(current) != metadata(entry) or metadata(after) != metadata(current):
            raise AdapterError("Cache content metadata changed while inspecting")
    finally:
        os.close(child)


def inventory(descriptor, cache_name="Index.noindex"):
    """Capture an inode-bound tree, rejecting links, user-looking content and mounts."""
    records, allocated = [], 0
    device = os.fstat(descriptor).st_dev

    def visit(fd, prefix):
        nonlocal allocated
        if prefix.count("/") >= 64:
            raise AdapterError("Cache exceeds the bounded directory depth")
        node = {"identity": identity(os.fstat(fd)), "children": {}}
        for name in sorted(os.listdir(fd)):
            if len(records) >= MAX_ENTRIES:
                raise AdapterError("Cache exceeds the bounded inventory budget")
            relative = f"{prefix}/{name}" if prefix else name
            entry = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if name.startswith(".") or Path(name).suffix.casefold() in PROTECTED_SUFFIXES:
                raise AdapterError(f"Protected or manually authored-looking content: {relative}")
            if entry.st_dev != device or entry.st_uid != os.getuid() or entry.st_mode & 0o022 or stat.S_ISLNK(entry.st_mode):
                raise AdapterError(f"Link, ownership or volume boundary: {relative}")
            signature = content_signature(cache_name, relative, stat.S_ISDIR(entry.st_mode))
            metadata = [entry.st_dev, entry.st_ino, entry.st_mode, entry.st_uid, entry.st_size, entry.st_mtime_ns, entry.st_ctime_ns]
            records.append([relative, metadata])
            allocated += entry.st_blocks * 512
            if stat.S_ISDIR(entry.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    if identity(os.fstat(child)) != identity(entry):
                        raise AdapterError("Directory changed while inventorying")
                    node["children"][name] = visit(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1:
                check_content(fd, name, entry, signature)
                node["children"][name] = {"identity": identity(entry), "metadata": metadata}
            else:
                raise AdapterError(f"Hard link or special file: {relative}")
        return node

    tree = visit(descriptor, "")
    digest = hashlib.sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest()
    return tree, digest, allocated, len(records)


def inspect_cache(repository, derived_data, workspace, name):
    repository, derived_data, workspace, binding = inspect_context(repository, derived_data, workspace)
    if name not in CACHES:
        raise AdapterError("Cache name is outside the closed allowlist")
    target = derived_data / name
    with directory(derived_data) as parent, directory(target) as descriptor:
        info = os.fstat(descriptor)
        if info.st_uid != os.getuid() or info.st_mode & 0o022 or info.st_dev != os.fstat(parent).st_dev:
            raise AdapterError("Cache ownership, permissions or volume boundary is unsafe")
        relative = target.relative_to(repository).as_posix()
        tracked = git(repository, "ls-files", "--", relative)
        ignored = git(repository, "check-ignore", "--no-index", "-q", "--", relative)
        if tracked.returncode or tracked.stdout or ignored.returncode != 0:
            raise AdapterError("Cache must be ignored by the repository and contain no tracked files")
        tree, digest, size, count = inventory(descriptor, name)
        paths = [relative]

        def collect(node, prefix):
            for child_name, child in node["children"].items():
                child_path = prefix + "/" + child_name
                paths.append(child_path)
                if "children" in child:
                    collect(child, child_path)

        collect(tree, relative)
        ignored_paths = git(repository, "check-ignore", "--no-index", "-z", "--stdin", input_text="\0".join(paths) + "\0")
        if ignored_paths.returncode or set(ignored_paths.stdout.rstrip("\0").split("\0")) != set(paths):
            raise AdapterError("Every cache entry must be ignored, including nested exceptions")
        return {
            "name": ADAPTER, "repositoryPath": str(repository), "derivedDataPath": str(derived_data),
            "workspacePath": str(workspace), "cacheName": name,
            "cacheIdentity": identity(os.fstat(descriptor)), "treeFingerprint": digest,
            "entryCount": count, "contentProfile": "empty-cache-v1" if count == 0 else "indexstore-v5-signature-v1", **binding,
        }, size, tree


def audit(repository, derived_data, workspace):
    repository, derived_data, workspace, binding = inspect_context(repository, derived_data, workspace)
    activity_problem = None
    try:
        check_activity()
    except AdapterError as error:
        activity_problem = str(error)
    candidates = []
    for name in CACHES:
        path = derived_data / name
        if not path.exists() and not path.is_symlink():
            continue
        problem, adapter, size = activity_problem, None, None
        try:
            adapter, size, _ = inspect_cache(repository, derived_data, workspace, name)
        except (OSError, AdapterError) as error:
            problem = str(error)
        candidates.append({
            "id": "xcode-" + name.lower().replace(".", "-"), "path": str(path),
            "resolvedPath": str(path.resolve()), "approvedRoot": str(repository), "class": "cache",
            "sizeBytes": size, "evidence": [problem or "Dedicated, ignored Xcode cache with matching WorkspacePath and no active builds"],
            "gitState": "ignored-untracked" if adapter else "unknown", "ownership": "project-dedicated",
            "risk": "requires-review" if problem else "safe-candidate",
            "auditRecommendation": "requires-review" if problem else "eligible-for-execution",
            "snapshot": {"observedAt": utc_now(), "isSymbolicLink": path.is_symlink(), "worktreeRole": "not-applicable"},
            "adapter": adapter,
        })
    return {"schemaVersion": 1, "auditId": f"xcode-{uuid.uuid4().hex}", "createdAt": utc_now(),
            "mode": "audit", "approvedRoots": [str(repository)], "approvedCandidateIds": [], "candidates": candidates}


def native_rename(source_fd, source, destination_fd, destination):
    if sys.platform != "darwin":
        raise AdapterError("Exclusive Xcode cache execution is supported on macOS only")
    library = ctypes.CDLL(None, use_errno=True)
    try:
        function = library.renameatx_np
    except AttributeError as error:
        raise AdapterError("Native exclusive rename is unavailable") from error
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(source_fd, os.fsencode(source), destination_fd, os.fsencode(destination), 0x00000004):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def save_descriptor(descriptor, data):
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    with os.fdopen(os.dup(descriptor), "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def create_output(path):
    path = canonical(Path(path).parent) / Path(path).name
    with directory(path.parent) as parent:
        try:
            return os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        except FileExistsError as error:
            raise AdapterError("Output already exists; it will not be overwritten") from error


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdapterError("Duplicate JSON object keys are not allowed")
        result[key] = value
    return result


def reject_constant(value):
    raise AdapterError("Non-finite JSON numbers are not allowed")


def finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        reject_constant(value)
    return number


def parse_json_object(contents):
    try:
        record = json.loads(contents, object_pairs_hook=unique_object,
                            parse_constant=reject_constant, parse_float=finite_number)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise AdapterError("Metadata is not a valid JSON object") from error
    if not isinstance(record, dict):
        raise AdapterError("Metadata must be a JSON object")
    return record


def read_json(path):
    path = Path(path)
    with directory(path.parent) as parent:
        contents = read_at(parent, path.name)
    return parse_json_object(contents), hashlib.sha256(contents).hexdigest()


def purge_contents(descriptor, tree):
    if set(os.listdir(descriptor)) != set(tree["children"]):
        raise AdapterError("Quarantined cache changed before purge")
    for name, expected in tree["children"].items():
        current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if identity(current) != expected["identity"] or stat.S_ISLNK(current.st_mode):
            raise AdapterError("Quarantined entry changed during purge")
        if "children" in expected:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            try:
                if identity(os.fstat(child)) != expected["identity"]:
                    raise AdapterError("Directory changed during purge")
                purge_contents(child, expected)
            finally:
                os.close(child)
            if identity(os.stat(name, dir_fd=descriptor, follow_symlinks=False)) != expected["identity"]:
                raise AdapterError("Directory changed before final removal")
            os.rmdir(name, dir_fd=descriptor)
        else:
            metadata = [current.st_dev, current.st_ino, current.st_mode, current.st_uid, current.st_size, current.st_mtime_ns, current.st_ctime_ns]
            if metadata != expected["metadata"] or current.st_nlink != 1:
                raise AdapterError("File changed during purge")
            os.unlink(name, dir_fd=descriptor)


def approved_candidate(manifest, manifest_digest, approval, candidate_id):
    """Check recorded consent and candidate bindings, not human identity or live safety."""
    if (type(manifest.get("schemaVersion")) is not int or manifest["schemaVersion"] != 1
            or manifest.get("mode") != "audit" or manifest.get("approvedCandidateIds") != []
            or not isinstance(manifest.get("auditId"), str) or not manifest["auditId"].strip()):
        raise AdapterError("Execution requires an unchanged audit-mode manifest")
    candidates = manifest.get("candidates", [])
    roots = manifest.get("approvedRoots")
    if not isinstance(candidates, list) or not all(isinstance(item, dict) for item in candidates):
        raise AdapterError("Manifest candidates must be an array of objects")
    if (not isinstance(roots, list) or not roots
            or not all(isinstance(root, str) and root.startswith("/") for root in roots)
            or len(roots) != len(set(roots))):
        raise AdapterError("Approved roots must be unique absolute path strings")
    identifiers = [item.get("id") for item in candidates]
    if not all(isinstance(item, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item) for item in identifiers):
        raise AdapterError("Candidate IDs must follow the manifest identifier contract")
    if len(identifiers) != len(set(identifiers)) or candidate_id not in identifiers:
        raise AdapterError("Candidate ID must exist exactly once")
    if approval.get("auditId") != manifest.get("auditId") or approval.get("manifestSha256") != manifest_digest:
        raise AdapterError("Approval does not bind this exact audit manifest")
    authorized = approval.get("authorizedCandidateIds")
    if not isinstance(authorized, list) or not all(isinstance(item, str) for item in authorized) or len(authorized) != len(set(authorized)) or not set(authorized) <= set(identifiers):
        raise AdapterError("Authorized IDs must be a unique closed subset of this audit")
    if candidate_id not in authorized or not isinstance(approval.get("authorizationReference"), str) or not approval["authorizationReference"].strip():
        raise AdapterError("Candidate has no recorded explicit authorization")
    if not all(isinstance(record.get(key), str) for record, key in ((approval, "authorizedAt"), (manifest, "createdAt"))):
        raise AdapterError("Audit and authorization timestamps must be strings")
    try:
        authorized_at = datetime.fromisoformat(approval["authorizedAt"].replace("Z", "+00:00"))
        created_at = datetime.fromisoformat(manifest["createdAt"].replace("Z", "+00:00"))
        if not created_at <= authorized_at <= datetime.now(timezone.utc):
            raise ValueError("Invalid approval interval")
    except (KeyError, ValueError, TypeError) as error:
        raise AdapterError("Authorization must follow the audit and cannot be future-dated") from error
    candidate = candidates[identifiers.index(candidate_id)]
    expected = candidate.get("adapter")
    snapshot = candidate.get("snapshot")
    if (candidate.get("class") != "cache" or candidate.get("ownership") != "project-dedicated"
            or candidate.get("gitState") != "ignored-untracked" or candidate.get("risk") != "safe-candidate"
            or candidate.get("auditRecommendation") != "eligible-for-execution"
            or not isinstance(snapshot, dict) or snapshot.get("isSymbolicLink") is not False
            or snapshot.get("worktreeRole") != "not-applicable"
            or type(candidate.get("sizeBytes")) is not int or candidate["sizeBytes"] < 0
            or not isinstance(expected, dict) or expected.get("name") != ADAPTER):
        raise AdapterError("Candidate is not eligible for this adapter")
    if any(not isinstance(expected.get(key), str) or not expected[key] for key in ("repositoryPath", "derivedDataPath", "workspacePath", "cacheName")):
        raise AdapterError("Adapter ownership paths must be nonempty strings")
    if set(expected) != {"name", "repositoryPath", "derivedDataPath", "workspacePath", "cacheName", "cacheIdentity",
                         "treeFingerprint", "entryCount", "derivedDataIdentity", "infoPlistSha256", "contentProfile"}:
        raise AdapterError("Recorded adapter metadata does not match the supported contract")
    repository, derived_data, workspace = map(Path, (expected["repositoryPath"], expected["derivedDataPath"], expected["workspacePath"]))
    target = derived_data / expected["cacheName"]
    if candidate.get("path") != str(target) or candidate.get("resolvedPath") != str(target) or candidate.get("approvedRoot") != str(repository) or str(repository) not in manifest.get("approvedRoots", []):
        raise AdapterError("Candidate path is not the approved dedicated cache")
    if expected["cacheName"] not in CACHES:
        raise AdapterError("Cache name is outside the closed allowlist")
    for key, path in (("repositoryPath", repository), ("derivedDataPath", derived_data), ("workspacePath", workspace)):
        if not path.is_absolute() or ".." in path.parts or str(path).startswith("//") or str(path) != expected[key]:
            raise AdapterError("Recorded ownership paths must be absolute and normalized")
    if repository not in derived_data.parents or repository not in workspace.parents:
        raise AdapterError("Recorded DerivedData and workspace must be inside the repository")
    if ".git" in derived_data.relative_to(repository).parts or workspace.suffix not in {".xcodeproj", ".xcworkspace"}:
        raise AdapterError("Unsupported recorded workspace or Git metadata path")
    for key in ("cacheIdentity", "derivedDataIdentity"):
        value = expected.get(key)
        if not isinstance(value, list) or len(value) != 2 or any(type(part) is not int or part < 0 for part in value):
            raise AdapterError("Recorded directory identities must be two nonnegative integers")
    for key in ("treeFingerprint", "infoPlistSha256"):
        if not isinstance(expected.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", expected[key]):
            raise AdapterError("Recorded fingerprints must be SHA-256 hex strings")
    if type(expected.get("entryCount")) is not int or not 0 <= expected["entryCount"] <= MAX_ENTRIES:
        raise AdapterError("Recorded inventory count exceeds the bounded contract")
    profile = "empty-cache-v1" if expected["entryCount"] == 0 else "indexstore-v5-signature-v1" if expected["cacheName"] == "Index.noindex" else None
    if profile is None or expected.get("contentProfile") != profile:
        raise AdapterError("Recorded cache lacks the supported generated-content profile")
    return candidate


def execute(manifest_path, approval_path, candidate_id, output_path):
    if sys.platform != "darwin":
        raise AdapterError("Xcode cache execution is macOS-only")
    manifest, manifest_digest = read_json(manifest_path)
    approval, approval_digest = read_json(approval_path)
    candidate = approved_candidate(manifest, manifest_digest, approval, candidate_id)
    expected = candidate["adapter"]
    repository, derived_data, workspace = map(Path, (expected["repositoryPath"], expected["derivedDataPath"], expected["workspacePath"]))
    target = derived_data / expected["cacheName"]
    check_activity()
    current, size, tree = inspect_cache(repository, derived_data, workspace, expected["cacheName"])
    if json.dumps(current, sort_keys=True) != json.dumps(expected, sort_keys=True) or size != candidate["sizeBytes"]:
        raise AdapterError("Cache identity, ownership or inventory changed since audit")
    output_fd = create_output(output_path)
    execution_id = uuid.uuid4().hex
    result = {"status": "prepared", "operation": "remove-xcode-cache", "executionId": execution_id, "auditId": manifest["auditId"],
              "candidateId": candidate_id, "manifestSha256": manifest_digest,
              "approvalSha256": approval_digest, "authorizedAt": approval["authorizedAt"],
              "authorizationReference": approval["authorizationReference"], "path": str(target),
              "journalPath": None, "journalSha256": None, "reason": None}
    moved = False
    purge_started = False
    journal_fd = None
    try:
        save_descriptor(output_fd, result)
        with ExitStack() as stack:
            parent = stack.enter_context(directory(derived_data))
            cache = stack.enter_context(directory(target))
            if identity(os.fstat(parent)) != expected["derivedDataIdentity"] or identity(os.fstat(cache)) != expected["cacheIdentity"]:
                raise AdapterError("Cache or parent was replaced before staging")
            stage_name = ".cleanup-staging-" + execution_id
            os.mkdir(stage_name, 0o700, dir_fd=parent)
            stage = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, stage)
            journal_fd = os.open("journal.json", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=stage)
            result["journalPath"] = str(derived_data / stage_name / "journal.json")
            # This recovery record is immutable after fsync: a later interrupted
            # outcome write must not destroy the metadata needed for restoration.
            journal = {"adapter": current, "payloadIdentity": expected["cacheIdentity"], "executionId": execution_id,
                       "auditId": manifest["auditId"], "candidateId": candidate_id,
                       "manifestSha256": manifest_digest, "approvalSha256": approval_digest,
                       "authorizedAt": approval["authorizedAt"], "authorizationReference": approval["authorizationReference"],
                       "createdAt": utc_now()}
            save_descriptor(journal_fd, journal)
            result["journalSha256"] = hashlib.sha256(read_at(stage, "journal.json")).hexdigest()
            os.fsync(stage)
            os.fsync(parent)
            save_descriptor(output_fd, result)
            native_rename(parent, expected["cacheName"], stage, "payload")
            moved = True
            os.fsync(stage)
            os.fsync(parent)
            payload = os.stat("payload", dir_fd=stage, follow_symlinks=False)
            if identity(payload) != expected["cacheIdentity"]:
                raise AdapterError("Staged object identity differs; retained without purge")
            check_activity()
            staged_tree, digest, _, _ = inventory(cache, expected["cacheName"])
            if digest != expected["treeFingerprint"]:
                raise AdapterError("Staged cache changed; retained without purge")
            result["status"] = "purging"
            save_descriptor(output_fd, result)
            purge_started = True
            purge_contents(cache, staged_tree)
            if identity(os.stat("payload", dir_fd=stage, follow_symlinks=False)) != expected["cacheIdentity"]:
                raise AdapterError("Staging namespace changed; retained for inspection")
            os.rmdir("payload", dir_fd=stage)
            os.fsync(stage)
            result["status"] = "removed"
            save_descriptor(output_fd, result)
        return result
    except (OSError, AdapterError) as error:
        result.update(status="partial" if purge_started else "retained" if moved else "blocked", reason=str(error))
        try:
            save_descriptor(output_fd, result)
        except OSError as report_error:
            result["reportError"] = str(report_error)
        return result
    finally:
        if journal_fd is not None:
            os.close(journal_fd)
        os.close(output_fd)


def restore(journal_path, output_path):
    if sys.platform != "darwin":
        raise AdapterError("Exclusive restoration is macOS-only")
    journal_path = canonical(journal_path)
    record, journal_digest = read_json(journal_path)
    expected = record["adapter"]
    repository, derived_data, workspace = map(Path, (expected["repositoryPath"], expected["derivedDataPath"], expected["workspacePath"]))
    _, _, _, binding = inspect_context(repository, derived_data, workspace)
    if any(binding[key] != expected[key] for key in binding):
        raise AdapterError("DerivedData identity or workspace metadata changed since staging")
    if expected.get("name") != ADAPTER or journal_path.name != "journal.json" or journal_path.parent.parent != derived_data or not journal_path.parent.name.startswith(".cleanup-staging-") or expected["cacheName"] not in CACHES:
        raise AdapterError("Journal is not in its recorded staging directory")
    source_execution = record.get("executionId")
    if source_execution is not None and (not isinstance(source_execution, str) or not re.fullmatch(r"[0-9a-f]{32}", source_execution)
                                         or journal_path.parent.name != ".cleanup-staging-" + source_execution):
        raise AdapterError("Journal execution attempt does not match its staging directory")
    check_activity()
    output_fd = create_output(output_path)
    result = {"status": "prepared", "operation": "restore-xcode-cache", "executionId": uuid.uuid4().hex,
              "sourceExecutionId": record.get("executionId"), "journalSha256": journal_digest,
              "path": str(derived_data / expected["cacheName"]), "journalPath": str(journal_path),
              "mutationStarted": False, "phase": "prepared", "durability": "unconfirmed", "reason": None}
    moved = False
    try:
        save_descriptor(output_fd, result)
        with directory(derived_data) as parent, directory(journal_path.parent) as stage:
            if os.fstat(stage).st_uid != os.getuid() or stat.S_IMODE(os.fstat(stage).st_mode) != 0o700:
                raise AdapterError("Staging directory ownership or permissions changed")
            if identity(os.stat("payload", dir_fd=stage, follow_symlinks=False)) != record["payloadIdentity"]:
                raise AdapterError("Payload identity differs from the journal")
            native_rename(stage, "payload", parent, expected["cacheName"])
            moved = True
            result.update(mutationStarted=True, phase="renamed")
            os.fsync(stage)
            os.fsync(parent)
        result.update(status="restored", phase="completed", durability="confirmed")
        try:
            save_descriptor(output_fd, result)
        except OSError as report_error:
            result["reportError"] = str(report_error)
        return result
    except (OSError, AdapterError) as error:
        result.update(status="unknown" if moved else "blocked", reason=str(error))
        try:
            save_descriptor(output_fd, result)
        except OSError as report_error:
            result["reportError"] = str(report_error)
        if not moved:
            # Preserve the API's pre-mutation error contract; the CLI reports
            # blocked and the separately saved receipt records its phase.
            raise
        return result
    finally:
        os.close(output_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("audit")
    for name in ("repository", "derived-data", "workspace", "output"):
        inspect.add_argument("--" + name, type=Path, required=True)
    remove = commands.add_parser("execute")
    for name in ("manifest", "approval", "output"):
        remove.add_argument("--" + name, type=Path, required=True)
    remove.add_argument("--candidate", required=True)
    recovery = commands.add_parser("restore")
    recovery.add_argument("--journal", type=Path, required=True)
    recovery.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            result = audit(args.repository, args.derived_data, args.workspace)
            descriptor = create_output(args.output)
            try:
                save_descriptor(descriptor, result)
            finally:
                os.close(descriptor)
        elif args.command == "execute":
            result = execute(args.manifest, args.approval, args.candidate, args.output)
        else:
            result = restore(args.journal, args.output)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") in {None, "removed", "restored"} and not result.get("reportError") else 2
    except (OSError, AdapterError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
