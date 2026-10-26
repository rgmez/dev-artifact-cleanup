"""Validate immutable execution evidence and native receipts."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_xcode_cache import Fixture, xcode_cache

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "dev-artifact-cleanup" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_execution


class ValidationFixture(Fixture):
    def _records(self, status="removed", reason=None, journal=True):
        audit_path, approval_path, result_path = self._approval()
        audit = json.loads(audit_path.read_text())
        approval = json.loads(approval_path.read_text())
        candidate = audit["candidates"][0]
        audit_bytes = audit_path.read_bytes()
        approval_bytes = approval_path.read_bytes()
        staging = Path(candidate["adapter"]["derivedDataPath"]) / (".cleanup-staging-" + "a" * 32)
        origin = str(staging / "journal.json")
        result = {"operation": "remove-xcode-cache", "auditId": audit["auditId"],
                  "candidateId": candidate["id"], "manifestSha256": hashlib.sha256(audit_bytes).hexdigest(),
                  "approvalSha256": hashlib.sha256(approval_bytes).hexdigest(),
                  "authorizedAt": approval["authorizedAt"],
                  "authorizationReference": approval["authorizationReference"],
                  "path": candidate["path"], "status": status, "reason": reason,
                  "journalPath": origin if journal or status != "blocked" else None}
        result_path.write_text(json.dumps(result))
        journal_path = self.root / "archived-journal.json"
        if journal:
            journal = {"auditId": audit["auditId"], "candidateId": candidate["id"],
                       "manifestSha256": hashlib.sha256(audit_bytes).hexdigest(),
                       "approvalSha256": hashlib.sha256(approval_bytes).hexdigest(),
                       "authorizedAt": approval["authorizedAt"],
                       "authorizationReference": approval["authorizationReference"],
                       "adapter": candidate["adapter"],
                       "payloadIdentity": candidate["adapter"]["cacheIdentity"],
                       "createdAt": approval["authorizedAt"]}
            journal_path.write_text(json.dumps(journal))
        return audit_path, approval_path, result_path, journal_path

    def _validate(self, status="removed", reason=None, journal=True):
        paths = self._records(status, reason, journal)
        return validate_execution.validate_evidence(*paths[:3], paths[3] if journal else None)

    def _change(self, path, key, value):
        record = json.loads(path.read_text())
        record[key] = value
        path.write_text(json.dumps(record))

    def _rebind(self, paths):
        audit, approval, result, journal = paths
        data = json.loads(audit.read_text())
        audit_digest = hashlib.sha256(audit.read_bytes()).hexdigest()
        self._change(approval, "manifestSha256", audit_digest)
        approval_digest = hashlib.sha256(approval.read_bytes()).hexdigest()
        for path in (result, journal):
            self._change(path, "manifestSha256", audit_digest)
            self._change(path, "approvalSha256", approval_digest)
        self._change(journal, "adapter", data["candidates"][0]["adapter"])
        self._change(journal, "payloadIdentity", data["candidates"][0]["adapter"].get("cacheIdentity"))


class PortableValidationTests(ValidationFixture):
    def test_removed_is_valid_success(self):
        result = self._validate()
        self.assertTrue(result["valid"])
        self.assertTrue(result["reportedSuccess"])
        self.assertEqual(result["recommendedReviewStatus"], "completed")
        self.assertFalse(result["permissionGranted"])
        self.assertFalse(result["humanAuthorizationVerified"])

    def test_retained_and_partial_require_review_reason(self):
        for status in ("retained", "partial"):
            with self.subTest(status=status):
                result = self._validate(status, "activity changed")
                self.assertTrue(result["valid"])
                self.assertFalse(result["reportedSuccess"])
                self.assertEqual(result["recommendedReviewStatus"], "partial")

    def test_blocked_without_journal_is_valid(self):
        result = self._validate("blocked", "authorization stopped", False)
        self.assertTrue(result["valid"])
        self.assertEqual(result["outcome"], "blocked")

    def test_intermediate_or_missing_journal_is_invalid(self):
        for status in ("prepared", "purging"):
            self.assertFalse(self._validate(status, "not final")["valid"])
        self.assertFalse(self._validate("removed", None, False)["valid"])

    def test_archive_copy_works_when_target_is_missing(self):
        paths = self._records()
        original = Path(json.loads(paths[2].read_text())["journalPath"])
        self.assertFalse(original.exists())
        self.assertNotEqual(original, paths[3])
        # Even the recorded cache/repository need not survive evidence archival.
        (self.cache / "cache.pcm").unlink()
        self.cache.rmdir()
        self.assertTrue(validate_execution.validate_evidence(*paths)["valid"])

    def test_changed_inputs_and_bindings_are_invalid(self):
        audit, approval, result, journal = self._records()
        audit.write_bytes(audit.read_bytes() + b" \n")
        self.assertFalse(validate_execution.validate_evidence(audit, approval, result, journal)["valid"])
        audit, approval, result, journal = self._records()
        approval.write_bytes(approval.read_bytes() + b" ")
        self.assertFalse(validate_execution.validate_evidence(audit, approval, result, journal)["valid"])
        for key, value in (("payloadIdentity", "wrong"), ("manifestSha256", "0" * 64),
                           ("approvalSha256", "0" * 64), ("authorizationReference", "other")):
            with self.subTest(key=key):
                paths = self._records()
                self._change(paths[3], key, value)
                checked = validate_execution.validate_evidence(*paths)
                self.assertIn("journal.binding", {item["code"] for item in checked["findings"]})

    def test_journal_time_and_receipt_types_are_checked(self):
        audit, approval, result, journal = self._records()
        data = json.loads(journal.read_text()); data["createdAt"] = "2999-01-01T00:00:00+00:00"; journal.write_text(json.dumps(data))
        self.assertFalse(validate_execution.validate_evidence(audit, approval, result, journal)["valid"])
        paths = self._records()
        earlier = datetime.fromisoformat(json.loads(paths[1].read_text())["authorizedAt"]) - timedelta(seconds=1)
        self._change(paths[3], "createdAt", earlier.isoformat())
        self.assertFalse(validate_execution.validate_evidence(*paths)["valid"])
        for value in (True, [], None):
            paths = self._records()
            self._change(paths[2], "candidateId", value)
            self.assertFalse(validate_execution.validate_evidence(*paths)["valid"])

    def test_malformed_selected_metadata_is_invalid_even_when_bindings_match(self):
        mutations = (("cacheIdentity", [True, 2]), ("cacheIdentity", None),
                     ("derivedDataIdentity", [1]), ("treeFingerprint", "unknown"),
                     ("infoPlistSha256", "g" * 64), ("entryCount", True), ("entryCount", -1),
                     ("entryCount", xcode_cache.MAX_ENTRIES + 1))
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                paths = self._records()
                data = json.loads(paths[0].read_text())
                data["candidates"][0]["adapter"][key] = value
                paths[0].write_text(json.dumps(data))
                self._rebind(paths)
                checked = validate_execution.validate_evidence(*paths)
                self.assertIn("approval.binding", {item["code"] for item in checked["findings"]})

    def test_non_string_approval_time_is_a_finding_not_a_crash(self):
        paths = self._records()
        self._change(paths[1], "authorizedAt", [])
        self.assertFalse(validate_execution.validate_evidence(*paths)["valid"])

    def test_normalized_ownership_paths_are_required(self):
        paths = self._records()
        data = json.loads(paths[0].read_text())
        data["candidates"][0]["adapter"]["repositoryPath"] += "/."
        paths[0].write_text(json.dumps(data))
        self._rebind(paths)
        self.assertFalse(validate_execution.validate_evidence(*paths)["valid"])

    def test_failure_reasons_cannot_be_omitted_or_attached_to_success(self):
        for status, reason in (("retained", None), ("partial", ""), ("blocked", " "), ("removed", "failure")):
            with self.subTest(status=status):
                checked = self._validate(status, reason)
                self.assertFalse(checked["valid"])
                self.assertFalse(checked["reportedSuccess"])

    def test_invalid_journal_origins_never_trigger_path_discovery(self):
        for origin in (None, "/other/journal.json", str(self.derived_data / ".cleanup-staging-wrong" / "journal.json"),
                       str(self.derived_data) + "/./.cleanup-staging-" + "a" * 32 + "/journal.json"):
            with self.subTest(origin=origin):
                paths = self._records()
                self._change(paths[2], "journalPath", origin)
                self.assertFalse(validate_execution.validate_evidence(*paths)["valid"])

    def test_bare_preflight_block_is_incomplete_evidence(self):
        paths = self._records()
        paths[2].write_text(json.dumps({"status": "blocked", "reason": "preflight failed"}))
        checked = validate_execution.validate_evidence(*paths[:3])
        self.assertFalse(checked["valid"])
        self.assertEqual(checked["outcome"], "blocked")

    def test_input_symlinks_are_rejected(self):
        paths = self._records()
        link = self.root / "journal-link.json"
        link.symlink_to(paths[3])
        self.assertFalse(validate_execution.validate_evidence(*paths[:3], link)["valid"])

    def test_unknown_restore_and_malformed_duplicate_json_are_invalid(self):
        audit, approval, result, journal = self._records("restored", "no")
        self.assertFalse(validate_execution.validate_evidence(audit, approval, result, journal)["valid"])
        result.write_text('{"status": "removed", "status": "blocked"}')
        self.assertFalse(validate_execution.validate_evidence(audit, approval, result, journal)["valid"])

    def test_report_error_keeps_valid_but_not_success(self):
        audit, approval, result, journal = self._records(); data = json.loads(result.read_text()); data["reportError"] = "archive failed"; result.write_text(json.dumps(data))
        checked = validate_execution.validate_evidence(audit, approval, result, journal)
        self.assertTrue(checked["valid"]); self.assertFalse(checked["reportedSuccess"])

    def test_checker_is_read_only(self):
        paths = self._records()
        before = {p: Path(p).read_bytes() for p in paths[:3] + (paths[3],)}
        with patch.object(xcode_cache, "inspect_cache", side_effect=AssertionError("live inspection")), \
                patch.object(xcode_cache, "inspect_context", side_effect=AssertionError("live ownership")), \
                patch.object(xcode_cache, "check_activity", side_effect=AssertionError("process inspection")), \
                patch.object(xcode_cache, "git", side_effect=AssertionError("Git inspection")), \
                patch.object(xcode_cache, "execute", side_effect=AssertionError("execution")), \
                patch.object(xcode_cache, "restore", side_effect=AssertionError("restoration")):
            self.assertTrue(validate_execution.validate_evidence(*paths)["valid"])
        self.assertEqual(before, {p: Path(p).read_bytes() for p in before})

    def test_cli_output_collision_preserves_bytes_and_exits_two(self):
        audit, approval, result, journal = self._records()
        output = self.root / "collision.json"; output.write_bytes(b"keep")
        completed = subprocess.run([sys.executable, "-B", str(SCRIPTS / "validate_execution.py"),
                                    "--audit", str(audit), "--approval", str(approval), "--result", str(result),
                                    "--journal", str(journal), "--output", str(output)], capture_output=True)
        self.assertEqual(completed.returncode, 2); self.assertEqual(output.read_bytes(), b"keep")


@unittest.skipUnless(sys.platform == "darwin", "native macOS")
class NativeValidationTests(ValidationFixture):
    def test_native_removed_receipt_validates(self):
        paths = self._approval(); self._execute(paths)
        result = json.loads(paths[2].read_text()); journal = Path(result["journalPath"])
        self.assertTrue(validate_execution.validate_evidence(*paths[:2], paths[2], journal)["reportedSuccess"])

    def test_native_retained_receipt_validates(self):
        paths = self._approval()
        with patch.object(xcode_cache, "check_activity", side_effect=[None, xcode_cache.AdapterError("busy")]):
            self._execute(paths)
        result = json.loads(paths[2].read_text())
        self.assertEqual(result["status"], "retained")
        checked = validate_execution.validate_evidence(*paths, Path(result["journalPath"]))
        self.assertTrue(checked["valid"])
        self.assertFalse(checked["reportedSuccess"])

    def test_native_partial_receipt_validates(self):
        paths = self._approval()
        def interrupted(descriptor, tree):
            os.unlink("cache.pcm", dir_fd=descriptor)
            raise xcode_cache.AdapterError("Interrupted after one disposable file")

        with patch.object(xcode_cache, "purge_contents", side_effect=interrupted):
            self._execute(paths)
        result = json.loads(paths[2].read_text())
        self.assertEqual(result["status"], "partial")
        checked = validate_execution.validate_evidence(*paths, Path(result["journalPath"]))
        self.assertTrue(checked["valid"])
        self.assertFalse(checked["reportedSuccess"])
        self.assertEqual(checked["recommendedReviewStatus"], "partial")

    def test_native_blocked_after_journal_validates_without_claiming_success(self):
        paths = self._approval()
        with patch.object(xcode_cache, "native_rename", side_effect=OSError("fixture rename denied")):
            self._execute(paths)
        result = json.loads(paths[2].read_text())
        self.assertEqual(result["status"], "blocked")
        checked = validate_execution.validate_evidence(*paths, Path(result["journalPath"]))
        self.assertTrue(checked["valid"])
        self.assertFalse(checked["reportedSuccess"])
        self.assertTrue((self.cache / "cache.pcm").exists())
