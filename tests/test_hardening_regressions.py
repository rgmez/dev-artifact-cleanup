"""Regression coverage for hardened Xcode cache audit and recovery paths."""

import json
import hashlib
import os
from pathlib import Path
import stat
import sys
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import unittest

from test_execution_validation import ValidationFixture, validate_execution, xcode_cache


class PortableHardeningTests(ValidationFixture):
    def test_manual_files_inside_legacy_cache_require_review_and_remain(self):
        retained = {
            "README": b"Keep this README",
            "notes.rtf": b"Keep these notes",
            "generated.unknown": b"Keep this unknown file",
        }
        for name, contents in retained.items():
            with self.subTest(name=name):
                note = self.cache / name
                note.write_bytes(contents)
                try:
                    candidate = self._audit()["candidates"][0]
                    self.assertEqual(candidate["risk"], "requires-review")
                    self.assertEqual(candidate["auditRecommendation"], "requires-review")
                    self.assertEqual(note.read_bytes(), contents)
                finally:
                    note.unlink()

    def test_validation_rejects_a_journal_from_a_different_execution(self):
        paths = self._records()
        wrong_journal = self.root / "other-attempt-journal.json"
        data = json.loads(paths[3].read_text())
        data["executionId"] = "b" * 32
        wrong_journal.write_text(json.dumps(data))
        checked = validate_execution.validate_evidence(*paths[:3], wrong_journal)

        self.assertFalse(checked["valid"])
        self.assertFalse(checked["reportedSuccess"])

    def test_attempt_binding_is_checked_even_when_supplied_digest_matches(self):
        paths = self._records()
        self._change(paths[3], "executionId", "b" * 32)
        self._change(paths[2], "journalSha256", hashlib.sha256(paths[3].read_bytes()).hexdigest())
        checked = validate_execution.validate_evidence(*paths)
        self.assertFalse(checked["valid"])
        self.assertIn("journal.binding", {item["code"] for item in checked["findings"]})

    def test_journal_whitespace_change_is_not_the_recorded_journal(self):
        paths = self._records()
        paths[3].write_bytes(paths[3].read_bytes() + b"\n ")
        checked = validate_execution.validate_evidence(*paths)
        self.assertFalse(checked["valid"])
        self.assertIn("journal.digest", {item["code"] for item in checked["findings"]})

    def test_legacy_receipt_missing_attempt_and_journal_digest_is_incomplete(self):
        paths = self._records()
        result = json.loads(paths[2].read_text())
        result.pop("executionId")
        result.pop("journalSha256")
        paths[2].write_text(json.dumps(result))
        checked = validate_execution.validate_evidence(*paths)
        self.assertFalse(checked["valid"])
        self.assertFalse(checked["reportedSuccess"])

    def test_legacy_audit_without_content_profile_cannot_execute(self):
        paths = self._records()
        audit = json.loads(paths[0].read_text())
        audit["candidates"][0]["adapter"].pop("contentProfile")
        paths[0].write_text(json.dumps(audit))
        self._rebind(paths)
        checked = validate_execution.validate_evidence(*paths)
        self.assertFalse(checked["valid"])
        self.assertIn("approval.binding", {item["code"] for item in checked["findings"]})


@unittest.skipUnless(sys.platform == "darwin", "native macOS")
class NativeHardeningTests(ValidationFixture):
    def test_rename_failure_blocks_and_second_execution_succeeds_with_distinct_journal(self):
        paths = self._approval()
        rename = xcode_cache.native_rename
        calls = 0

        def fail_once(*arguments):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("fixture rename denied")
            return rename(*arguments)

        with patch.object(xcode_cache, "native_rename", side_effect=fail_once):
            blocked = self._execute(paths)

        self.assertEqual(blocked["status"], "blocked")
        journal_a = Path(blocked["journalPath"])
        self.assertTrue(journal_a.exists())
        self.assertTrue(self.cache.exists())
        journal_a_bytes = journal_a.read_bytes()

        second_paths = (paths[0], paths[1], self.root / "second-result.json")
        removed = self._execute(second_paths)
        journal_b = Path(removed["journalPath"])
        self.assertEqual(removed["status"], "removed")
        self.assertNotEqual(journal_a, journal_b)
        self.assertNotEqual(journal_a_bytes, journal_b.read_bytes())
        self.assertFalse(self.cache.exists())
        self.assertTrue(validate_execution.validate_evidence(*second_paths[:3], journal_b)["valid"])
        self.assertFalse(validate_execution.validate_evidence(*second_paths[:3], journal_a)["valid"])
        self.assertEqual(journal_a.read_bytes(), journal_a_bytes)

    def _retained_journal(self):
        paths = self._approval()
        with patch.object(xcode_cache, "check_activity", side_effect=[None, xcode_cache.AdapterError("busy")]):
            result = self._execute(paths)
        return Path(result["journalPath"])

    def test_restore_initial_receipt_failure_does_not_move_payload(self):
        journal = self._retained_journal()
        with patch.object(xcode_cache, "save_descriptor", side_effect=OSError("fixture result unavailable")):
            with self.assertRaises(OSError):
                xcode_cache.restore(journal, self.root / "restore.json")
        self.assertFalse(self.cache.exists())
        self.assertTrue((journal.parent / "payload" / self.cache_relative).exists())

    def test_restore_final_result_write_failure_reports_actual_completed_move(self):
        journal = self._retained_journal()
        save = xcode_cache.save_descriptor

        def fail_final(descriptor, record):
            if record["status"] == "restored":
                raise OSError("fixture final result unavailable")
            return save(descriptor, record)

        output = self.root / "restore.json"
        with patch.object(xcode_cache, "save_descriptor", side_effect=fail_final), \
                patch.object(sys, "argv", ["xcode_cache.py", "restore", "--journal", str(journal), "--output", str(output)]):
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = xcode_cache.main()
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertTrue(self.cache_file.exists())
        self.assertEqual(self.cache_file.read_bytes(), self.cache_bytes)
        self.assertEqual(receipt["status"], "restored")
        self.assertTrue(receipt["mutationStarted"])
        self.assertEqual(receipt["durability"], "confirmed")
        self.assertIn("reportError", receipt)
        self.assertEqual(json.loads(output.read_text())["status"], "prepared")

    def test_legacy_journal_can_be_recovered_without_inventing_source_attempt(self):
        journal = self._retained_journal()
        legacy = json.loads(journal.read_text())
        legacy.pop("executionId")
        legacy["adapter"].pop("contentProfile")
        journal.write_text(json.dumps(legacy))
        restored = xcode_cache.restore(journal, self.root / "restore.json")
        self.assertEqual(restored["status"], "restored")
        self.assertIsNone(restored["sourceExecutionId"])
        self.assertEqual(restored["journalSha256"], hashlib.sha256(journal.read_bytes()).hexdigest())
        self.assertEqual(self.cache_file.read_bytes(), self.cache_bytes)

    def test_restore_reports_unknown_after_directory_fsync_failure(self):
        paths = self._approval()
        with patch.object(
            xcode_cache, "check_activity", side_effect=[None, xcode_cache.AdapterError("busy")]
        ):
            retained = self._execute(paths)
        journal = Path(retained["journalPath"])
        output = self.root / "restore.json"
        moved = False
        native_rename = xcode_cache.native_rename
        real_fsync = os.fsync

        def mark_rename(*arguments):
            nonlocal moved
            result = native_rename(*arguments)
            moved = True
            return result

        def fail_directory_fsync(fd):
            if moved and stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("fixture directory durability failure")
            return real_fsync(fd)

        with patch.object(xcode_cache, "native_rename", side_effect=mark_rename), patch.object(
            xcode_cache.os, "fsync", side_effect=fail_directory_fsync
        ), patch.object(xcode_cache.sys, "argv", ["xcode_cache.py", "restore", "--journal", str(journal), "--output", str(output)]):
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = xcode_cache.main()

        receipt = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertTrue(self.cache.exists())
        self.assertTrue((self.cache_file).exists())
        self.assertFalse((journal.parent / "payload").exists())
        self.assertEqual(receipt["status"], "unknown")
        self.assertTrue(receipt["mutationStarted"])
        self.assertEqual(receipt["phase"], "renamed")
        self.assertEqual(receipt["durability"], "unconfirmed")
        self.assertEqual(json.loads(output.read_text()), receipt)


if __name__ == "__main__":
    unittest.main()
