"""Strict JSON and approval-boundary regression tests for the Xcode adapter."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_xcode_cache import Fixture, xcode_cache


class PortableRecordTests(unittest.TestCase):
    def test_read_json_rejects_duplicate_keys_at_any_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "record.json"
            path.write_text('{"outer": {"value": 1, "value": 2}}')
            with self.assertRaises(xcode_cache.AdapterError):
                xcode_cache.read_json(path)

    def test_read_json_rejects_non_finite_numbers(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                path = Path(directory).resolve() / "record.json"
                path.write_text('{"value": ' + value + '}')
                with self.assertRaises(xcode_cache.AdapterError):
                    xcode_cache.read_json(path)

    def test_deep_invalid_json_returns_a_blocking_adapter_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "record.json"
            path.write_text('[' * 2000 + '0' + ']' * 2000)
            with self.assertRaises(xcode_cache.AdapterError):
                xcode_cache.read_json(path)

    def test_valid_record_preserves_exact_byte_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "record.json"
            data = b'{"value": 1.5, "nested": {"enabled": true}}\n'
            path.write_bytes(data)
            record, digest = xcode_cache.read_json(path)
            self.assertEqual(record, {"value": 1.5, "nested": {"enabled": True}})
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())

    def test_read_json_rejects_non_object_roots(self):
        for value in ("[]", "null", "true", "42", '"str"'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                path = Path(directory).resolve() / "record.json"
                path.write_text(value)
                with self.assertRaises(xcode_cache.AdapterError):
                    xcode_cache.read_json(path)


@unittest.skipUnless(sys.platform == "darwin", "native macOS")
class NativeApprovalTests(Fixture):
    def _synthetic_execute(self, mutate):
        manifest_path, approval_path, output = self._approval()
        manifest = json.loads(manifest_path.read_text())
        mutate(manifest)
        raw = json.dumps(manifest, sort_keys=True).encode()
        manifest_path.write_bytes(raw)
        approval = json.loads(approval_path.read_text())
        approval["auditId"] = manifest["auditId"]
        approval["manifestSha256"] = hashlib.sha256(raw).hexdigest()
        candidates = manifest.get("candidates")
        requested = "xcode-index-noindex"
        if isinstance(candidates, list) and candidates:
            requested = candidates[0]["id"]
            approval["authorizedCandidateIds"] = [requested]
        approval_path.write_text(json.dumps(approval))
        with self.assertRaises(xcode_cache.AdapterError):
            xcode_cache.execute(manifest_path, approval_path, requested, output)
        self.assertTrue((self.cache_file).exists())
        self.assertFalse(output.exists())
        self.assertEqual(list(self.derived_data.glob(".cleanup-staging-*")), [])

    def test_non_cache_candidate_class_is_rejected(self):
        self._synthetic_execute(lambda m: m["candidates"][0].update({"class": "archive"}))

    def test_unknown_ownership_is_rejected(self):
        self._synthetic_execute(lambda m: m["candidates"][0].update(ownership="unknown"))

    def test_dirty_git_state_is_rejected(self):
        self._synthetic_execute(lambda m: m["candidates"][0].update(gitState="dirty"))

    def test_boolean_schema_version_is_rejected(self):
        self._synthetic_execute(lambda m: m.update(schemaVersion=True))

    def test_non_object_snapshot_is_rejected(self):
        self._synthetic_execute(lambda m: m["candidates"][0].update(snapshot=[]))

    def test_non_list_candidates_is_rejected(self):
        self._synthetic_execute(lambda m: m.update(candidates={}))

    def test_approved_roots_cannot_be_a_string(self):
        self._synthetic_execute(lambda m: m.update(approvedRoots=m["approvedRoots"][0]))

    def test_size_must_match_audit_inventory(self):
        self._synthetic_execute(lambda m: m["candidates"][0].update(sizeBytes=123))

    def test_candidate_id_must_be_string(self):
        self._synthetic_execute(lambda m: m["candidates"][0].update(id=42))

    def test_candidate_id_pattern_is_rejected(self):
        self._synthetic_execute(lambda m: m["candidates"][0].update(id="INVALID ID!"))

    def test_duplicate_authorized_ids_are_rejected_before_staging(self):
        manifest_path, approval_path, output = self._approval()
        approval = json.loads(approval_path.read_text())
        approval_path.write_text(
            json.dumps(approval).replace(
                '"authorizedCandidateIds": ["xcode-index-noindex"]',
                '"authorizedCandidateIds": [], "authorizedCandidateIds": ["xcode-index-noindex"]',
            )
        )
        with self.assertRaises(xcode_cache.AdapterError):
            self._execute((manifest_path, approval_path, output))
        self.assertTrue((self.cache_file).exists())
        self.assertFalse(output.exists())
        self.assertEqual(list(self.derived_data.glob(".cleanup-staging-*")), [])

    def test_duplicate_audit_id_is_rejected_before_staging(self):
        manifest_path, approval_path, output = self._approval()
        manifest = json.loads(manifest_path.read_text())
        raw = json.dumps(manifest, sort_keys=True).replace(
            '"auditId": "' + manifest["auditId"] + '"',
            '"auditId": "' + manifest["auditId"] + '", "auditId": "' + manifest["auditId"] + '"',
            1,
        ).encode()
        manifest_path.write_bytes(raw)
        approval = json.loads(approval_path.read_text())
        approval["manifestSha256"] = hashlib.sha256(raw).hexdigest()
        approval_path.write_text(json.dumps(approval))
        with self.assertRaises(xcode_cache.AdapterError):
            self._execute((manifest_path, approval_path, output))
        self.assertTrue((self.cache_file).exists())
        self.assertFalse(output.exists())
        self.assertEqual(list(self.derived_data.glob(".cleanup-staging-*")), [])

    def test_result_and_journal_bind_exact_approval(self):
        paths = self._approval()
        approval_bytes = paths[1].read_bytes()
        approval = json.loads(approval_bytes)
        result = self._execute(paths)
        journal = json.loads(Path(result["journalPath"]).read_text())
        self.assertEqual(result["status"], "removed")
        for record in (result, journal):
            self.assertEqual(record["approvalSha256"], hashlib.sha256(approval_bytes).hexdigest())
            self.assertEqual(record["authorizedAt"], approval["authorizedAt"])
            self.assertEqual(record["authorizationReference"], approval["authorizationReference"])
