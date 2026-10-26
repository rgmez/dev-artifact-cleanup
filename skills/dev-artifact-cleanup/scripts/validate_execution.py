#!/usr/bin/env python3
"""Check Xcode removal evidence without inspecting or modifying project artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

# CLI use must not create bytecode inside a pinned, hash-verified skill package.
sys.dont_write_bytecode = True
import xcode_cache as cache


OUTCOMES = {"removed", "retained", "partial", "blocked", "prepared", "purging"}


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except ValueError:
        return None


def same(left, right):
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def validate_evidence(audit_path, approval_path, result_path, journal_path=None):
    """Validate recorded relationships, never grant execution or certify authenticity."""
    findings, documents, digests = [], {}, {}

    def flag(code, message):
        findings.append({"code": code, "message": message})

    for name, path in (("audit", audit_path), ("approval", approval_path), ("result", result_path), ("journal", journal_path)):
        if path is None:
            continue
        try:
            path = Path(path)
            with cache.directory(path.parent) as parent:
                contents = cache.read_at(parent, path.name)
            digests[name] = hashlib.sha256(contents).hexdigest()
            documents[name] = cache.parse_json_object(contents)
        except (OSError, ValueError, TypeError, cache.AdapterError) as error:
            flag("input." + name, str(error))

    result = documents.get("result", {})
    status = result.get("status")
    status = status if isinstance(status, str) and status in OUTCOMES else "unknown"

    def finish():
        valid = not findings
        success = valid and status == "removed" and not result.get("reportError")
        review_status = "completed" if success else "partial" if status in {"removed", "retained", "partial", "prepared", "purging"} else "blocked"
        return {"schemaVersion": 1, "valid": valid, "permissionGranted": False,
                "humanAuthorizationVerified": False, "reportedSuccess": success,
                "outcome": status, "recommendedReviewStatus": review_status,
                "validatedAt": datetime.now(timezone.utc).isoformat(),
                "inputSha256": digests, "findings": findings}

    if any(name not in documents for name in ("audit", "approval", "result")):
        return finish()
    audit, approval = documents["audit"], documents["approval"]
    try:
        candidate = cache.approved_candidate(audit, digests["audit"], approval, result.get("candidateId"))
    except (cache.AdapterError, ValueError, TypeError, KeyError) as error:
        flag("approval.binding", str(error))
        return finish()

    expected = candidate["adapter"]
    bindings = {"operation": "remove-xcode-cache", "auditId": audit["auditId"], "candidateId": candidate["id"],
                "manifestSha256": digests["audit"], "approvalSha256": digests["approval"],
                "authorizedAt": approval["authorizedAt"], "authorizationReference": approval["authorizationReference"],
                "path": candidate["path"]}
    for key, value in bindings.items():
        if not same(result.get(key), value):
            flag("result.binding", "Result does not bind the recorded " + key)
    if status == "unknown":
        flag("result.status", "Unsupported or missing removal outcome; restoration uses a separate authorization workflow")
    if "reason" not in result or result["reason"] is not None and not isinstance(result["reason"], str):
        flag("result.reason", "Result reason must be recorded as text or null")
    if status in {"retained", "partial", "blocked"} and not (isinstance(result.get("reason"), str) and result["reason"].strip()):
        flag("result.reason", "Unsuccessful outcomes need a recorded reason")
    if status == "removed" and result.get("reason") is not None:
        flag("result.reason", "A successful removal cannot also record a failure reason")
    if "reportError" in result and not (isinstance(result["reportError"], str) and result["reportError"].strip()):
        flag("result.report-error", "A report-write error must be nonempty text")
    if status in {"prepared", "purging"}:
        flag("result.nonterminal", "An intermediate receipt cannot establish a final outcome")

    origin = result.get("journalPath")
    needs_journal = status in {"removed", "retained", "partial"} or origin is not None
    if "journalPath" not in result:
        flag("journal.origin", "Result lacks its original journal path or explicit null")
    if needs_journal:
        if not isinstance(origin, str):
            flag("journal.origin", "This outcome requires the original journal path")
        else:
            path = Path(origin)
            if (not path.is_absolute() or str(path) != origin or ".." in path.parts
                    or path.name != "journal.json" or path.parent.parent != Path(expected["derivedDataPath"])
                    or not re.fullmatch(r"\.cleanup-staging-[0-9a-f]{32}", path.parent.name)):
                flag("journal.origin", "Journal origin is not a dedicated staging path for this audit")
        if journal_path is None:
            flag("journal.missing", "Provide the original journal bytes or their preserved archive copy")
    elif journal_path is not None:
        flag("journal.unexpected", "A journal was supplied without a recorded origin")

    journal = documents.get("journal")
    if journal is not None:
        journal_bindings = {key: bindings[key] for key in ("auditId", "candidateId", "manifestSha256", "approvalSha256", "authorizedAt", "authorizationReference")}
        journal_bindings.update(adapter=expected, payloadIdentity=expected.get("cacheIdentity"))
        for key, value in journal_bindings.items():
            if not same(journal.get(key), value):
                flag("journal.binding", "Journal does not bind the recorded " + key)
        created = timestamp(journal.get("createdAt"))
        authorized = timestamp(approval.get("authorizedAt"))
        if created is None or authorized is None or not authorized <= created <= datetime.now(timezone.utc):
            flag("journal.timestamp", "Journal time must follow approval and cannot be future-dated")
    return finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("audit", "approval", "result"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_evidence(args.audit, args.approval, args.result, args.journal)
    if args.output:
        try:
            descriptor = cache.create_output(args.output)
            try:
                cache.save_descriptor(descriptor, result)
            finally:
                os.close(descriptor)
        except (OSError, ValueError, TypeError, cache.AdapterError) as error:
            result["valid"] = False
            result["reportedSuccess"] = False
            result["recommendedReviewStatus"] = "partial"
            result["findings"].append({"code": "output.write", "message": str(error)})
            print(json.dumps(result, indent=2))
            return 2
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
