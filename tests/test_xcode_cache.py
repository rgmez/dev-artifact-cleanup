"""Exercise the adapter only against disposable, isolated Git repositories."""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "dev-artifact-cleanup" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import xcode_cache


class Fixture(unittest.TestCase):
    cache_relative = Path("DataStore/v5/records/AA/fixture.c-0123456789ABC")
    # Header-shaped unit data, not a captured real compiler index. The separate
    # native profile test below exercises actual Clang output.
    cache_bytes = b"IDXR\x01\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"

    def setUp(self):
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name).resolve()
        self.repository = self.root / "repository"
        self.derived_data = self.repository / ".derivedData"
        self.workspace = self.repository / "Demo.xcodeproj"
        self.repository.mkdir()
        self.workspace.mkdir()
        self._git("init", "--template=", "-b", "develop")
        self._git("config", "user.name", "Fixture")
        self._git("config", "user.email", "fixture@example.invalid")
        (self.repository / "README.md").write_text("Disposable fixture\n")
        (self.repository / ".gitignore").write_text(".derivedData/\n")
        self._git("add", "README.md", ".gitignore")
        self._git("commit", "-m", "New: Add disposable Xcode fixture")
        self._write_cache()
        activity = patch.object(xcode_cache, "check_activity", return_value=None)
        activity.start()
        self.addCleanup(activity.stop)

    @property
    def cache(self):
        return self.derived_data / "Index.noindex"

    @property
    def cache_file(self):
        return self.cache / self.cache_relative

    def _remove_fixture_cache(self):
        self.cache_file.unlink()
        for path in self.cache_file.parents:
            if path == self.derived_data:
                break
            path.rmdir()

    def _git(self, *args):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
        subprocess.run(["git", "-c", f"core.hooksPath={os.devnull}", "-c", "commit.gpgSign=false", *args],
                       cwd=self.repository, env=environment, check=True, capture_output=True)

    def _write_cache(self, name="Index.noindex"):
        self.derived_data.mkdir(exist_ok=True)
        (self.derived_data / "info.plist").write_bytes(plistlib.dumps({"WorkspacePath": str(self.workspace)}))
        cache = self.derived_data / name
        cache.mkdir()
        generated = cache / self.cache_relative
        generated.parent.mkdir(parents=True)
        generated.write_bytes(self.cache_bytes)

    def _audit(self):
        return xcode_cache.audit(self.repository, self.derived_data, self.workspace)

    def _approval(self):
        manifest = self._audit()
        manifest_path, approval_path = self.root / "manifest.json", self.root / "approval.json"
        raw = json.dumps(manifest, sort_keys=True).encode()
        manifest_path.write_bytes(raw)
        approval = {
            "auditId": manifest["auditId"], "manifestSha256": hashlib.sha256(raw).hexdigest(),
            "authorizedCandidateIds": ["xcode-index-noindex"], "authorizedAt": xcode_cache.utc_now(),
            "authorizationReference": "Explicit approval for this disposable test fixture only",
        }
        approval_path.write_text(json.dumps(approval))
        return manifest_path, approval_path, self.root / "result.json"

    def _execute(self, paths):
        return xcode_cache.execute(paths[0], paths[1], "xcode-index-noindex", paths[2])

    def _requires_review(self):
        candidate = self._audit()["candidates"][0]
        self.assertEqual(candidate["risk"], "requires-review")
        self.assertEqual(candidate["auditRecommendation"], "requires-review")
        self._validate_schema(self._audit())
        return candidate

    def _validate_schema(self, manifest):
        schema_path = SCRIPTS.parent / "references" / "audit-manifest.schema.json"
        schema = json.loads(schema_path.read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(manifest)


class AuditTests(Fixture):
    def test_audit_does_not_mutate_and_produces_eligible_candidate(self):
        before = {p.relative_to(self.repository).as_posix(): p.stat().st_mtime_ns for p in self.repository.rglob("*")}
        manifest = self._audit()
        self._validate_schema(manifest)
        after = {p.relative_to(self.repository).as_posix(): p.stat().st_mtime_ns for p in self.repository.rglob("*")}
        self.assertEqual(before, after)
        self.assertEqual(manifest["approvedCandidateIds"], [])
        candidate = manifest["candidates"][0]
        self.assertEqual(candidate["risk"], "safe-candidate")
        self.assertEqual(candidate["adapter"]["name"], xcode_cache.ADAPTER)
        self.assertIsInstance(candidate["sizeBytes"], int)

    def test_only_direct_allowlisted_caches_are_candidates(self):
        for name in xcode_cache.CACHES[1:]:
            self._write_cache(name)
        for name in ("SourcePackages", "Build", "Logs", "Archives", "random-cache"):
            (self.derived_data / name).mkdir()
            (self.derived_data / name / "evidence.md").write_text("Keep me")
        self.assertEqual({Path(c["path"]).name for c in self._audit()["candidates"]}, set(xcode_cache.CACHES))

    def test_no_cache_is_a_valid_empty_audit(self):
        self._remove_fixture_cache()
        manifest = self._audit()
        self.assertEqual(manifest["candidates"], [])
        self._validate_schema(manifest)

    def test_protected_files_outside_cache_do_not_make_them_targets(self):
        evidence = self.derived_data / "README.md"
        evidence.write_text("Retained evidence")
        self.assertEqual(self._audit()["candidates"][0]["risk"], "safe-candidate")
        self.assertEqual(evidence.read_text(), "Retained evidence")

    def test_wrong_workspace_is_rejected(self):
        (self.derived_data / "info.plist").write_bytes(plistlib.dumps({"WorkspacePath": "/wrong/Demo.xcodeproj"}))
        with self.assertRaises(xcode_cache.AdapterError):
            self._audit()

    def test_missing_metadata_is_rejected(self):
        (self.derived_data / "info.plist").unlink()
        with self.assertRaises((OSError, xcode_cache.AdapterError)):
            self._audit()

    def test_special_metadata_is_rejected_without_blocking_open(self):
        metadata = self.derived_data / "info.plist"
        metadata.unlink()
        os.mkfifo(metadata)
        with self.assertRaises(xcode_cache.AdapterError):
            self._audit()

    def test_secondary_worktree_is_rejected(self):
        secondary = self.root / "secondary"
        self._git("worktree", "add", "-b", "feature/secondary_fixture", str(secondary))
        self.repository = secondary
        self.workspace = secondary / "Demo.xcodeproj"
        self.derived_data = secondary / ".derivedData"
        self.workspace.mkdir()
        self._write_cache()
        with self.assertRaises(xcode_cache.AdapterError):
            self._audit()

    def test_shared_external_derived_data_is_rejected(self):
        external = self.root / "shared-derived-data"
        external.mkdir()
        with self.assertRaises(xcode_cache.AdapterError):
            xcode_cache.audit(self.repository, external, self.workspace)

    def test_symlink_cache_is_review_only(self):
        self._remove_fixture_cache()
        self.cache.symlink_to(self.root, target_is_directory=True)
        candidate = self._requires_review()
        self.assertTrue(candidate["snapshot"]["isSymbolicLink"])
        self.assertIsNone(candidate["sizeBytes"])

    def test_symlink_inside_cache_is_review_only(self):
        (self.cache / "external").symlink_to(self.root, target_is_directory=True)
        self._requires_review()

    def test_symlink_path_component_is_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.repository, target_is_directory=True)
        with self.assertRaises(xcode_cache.AdapterError):
            xcode_cache.audit(alias, alias / ".derivedData", alias / "Demo.xcodeproj")

    def test_protected_content_inside_cache_is_review_only(self):
        for name in ("README.md", "screen.png", "release.xcarchive", "tests.xcresult", "source.swift", ".env"):
            with self.subTest(name=name):
                protected = self.cache / name
                protected.write_text("Keep me")
                self._requires_review()
                protected.unlink()

    def test_hard_link_is_review_only(self):
        os.link(self.cache_file, self.root / "copy.pcm")
        self._requires_review()

    def test_shared_writable_cache_is_review_only(self):
        self.cache.chmod(0o777)
        self._requires_review()

    def test_foreign_owned_cache_is_review_only(self):
        with patch.object(xcode_cache.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises(xcode_cache.AdapterError):
                self._audit()

    def test_unignored_cache_is_review_only(self):
        (self.repository / ".gitignore").write_text("")
        self._requires_review()

    def test_inventory_limits_fail_closed(self):
        with patch.object(xcode_cache, "MAX_ENTRIES", 0):
            self._requires_review()

    def test_nested_unignored_exception_is_review_only(self):
        (self.repository / ".gitignore").write_text(".derivedData/*\n!.derivedData/Index.noindex/\n.derivedData/Index.noindex/*\n!.derivedData/Index.noindex/DataStore/v5/records/AA/fixture.c-0123456789ABC\n")
        self._requires_review()

    def test_tracked_cache_is_review_only(self):
        self._git("add", "-f", ".derivedData/Index.noindex/" + self.cache_relative.as_posix())
        self._requires_review()

    def test_unknown_activity_is_review_only(self):
        with patch.object(xcode_cache, "check_activity", side_effect=xcode_cache.AdapterError("unknown")):
            self._requires_review()

    def test_git_environment_cannot_redirect_repository(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "missing"), "GIT_WORK_TREE": "/"}):
            self.assertEqual(self._audit()["candidates"][0]["risk"], "safe-candidate")


@unittest.skipUnless(sys.platform == "darwin", "Native execution is macOS-only; audit tests remain portable")
class NativeExecutionTests(Fixture):
    def test_valid_execution_removes_only_cache_and_leaves_journal(self):
        evidence = self.derived_data / "retained.md"
        evidence.write_text("Keep")
        result = self._execute(self._approval())
        self.assertEqual(result["status"], "removed")
        self.assertFalse(self.cache.exists())
        self.assertTrue(Path(result["journalPath"]).is_file())
        self.assertEqual(evidence.read_text(), "Keep")
        self.assertEqual(json.loads(Path(result["journalPath"]).read_text())["candidateId"], result["candidateId"])

    def test_bad_approval_and_unknown_ids_are_blocked(self):
        paths = self._approval()
        approval = json.loads(paths[1].read_text())
        for changes in ({"auditId": "wrong"}, {"manifestSha256": "0" * 64},
                        {"authorizedCandidateIds": []}, {"authorizedCandidateIds": ["xcode-index-noindex", "extra"]},
                        {"authorizedCandidateIds": ["xcode-index-noindex"] * 2},
                        {"authorizedAt": "2999-01-01T00:00:00Z"}, {"authorizationReference": ""}):
            with self.subTest(changes=changes):
                paths[1].write_text(json.dumps({**approval, **changes}))
                with self.assertRaises(xcode_cache.AdapterError):
                    self._execute(paths)
                self.assertTrue(self.cache.exists())

    def test_manifest_change_invalidates_approval(self):
        paths = self._approval()
        paths[0].write_bytes(paths[0].read_bytes() + b"\n")
        with self.assertRaises(xcode_cache.AdapterError):
            self._execute(paths)

    def test_changed_cache_is_blocked_before_mutation(self):
        paths = self._approval()
        (self.cache_file).write_bytes(b"Changed after audit")
        with self.assertRaises(xcode_cache.AdapterError):
            self._execute(paths)
        self.assertTrue(self.cache.exists())

    def test_unknown_activity_blocks_execution(self):
        paths = self._approval()
        with patch.object(xcode_cache, "check_activity", side_effect=xcode_cache.AdapterError("unknown")):
            with self.assertRaises(xcode_cache.AdapterError):
                self._execute(paths)
        self.assertTrue(self.cache.exists())

    def test_output_collision_does_not_overwrite_or_move(self):
        paths = self._approval()
        paths[2].write_text("User document")
        with self.assertRaises(xcode_cache.AdapterError):
            self._execute(paths)
        self.assertEqual(paths[2].read_text(), "User document")
        self.assertTrue(self.cache.exists())
        self.assertFalse(list(self.derived_data.glob(".cleanup-staging-*")))

    def _retained(self):
        paths = self._approval()
        with patch.object(xcode_cache, "check_activity", side_effect=[None, xcode_cache.AdapterError("Build started")]):
            result = self._execute(paths)
        self.assertEqual(result["status"], "retained")
        return result

    def test_post_staging_activity_retains_and_can_restore(self):
        result = self._retained()
        self.assertFalse(self.cache.exists())
        journal = Path(result["journalPath"])
        self.assertEqual((journal.parent / "payload" / self.cache_relative).read_bytes(), self.cache_bytes)
        restored = xcode_cache.restore(journal, self.root / "restore.json")
        self.assertEqual(restored["status"], "restored")
        self.assertEqual((self.cache_file).read_bytes(), self.cache_bytes)

    def test_restore_never_overwrites_recreated_cache(self):
        result = self._retained()
        self.cache.mkdir()
        (self.cache / "new.pcm").write_bytes(b"New build")
        journal = Path(result["journalPath"])
        with self.assertRaises((OSError, xcode_cache.AdapterError)):
            xcode_cache.restore(journal, self.root / "restore.json")
        self.assertEqual((self.cache / "new.pcm").read_bytes(), b"New build")
        self.assertTrue((journal.parent / "payload" / self.cache_relative).exists())

    def test_restore_blocks_changed_workspace_metadata(self):
        result = self._retained()
        metadata = self.derived_data / "info.plist"
        metadata.write_bytes(metadata.read_bytes() + b"\n")
        with self.assertRaises(xcode_cache.AdapterError):
            xcode_cache.restore(Path(result["journalPath"]), self.root / "restore.json")

    def test_object_replaced_during_staging_is_not_purged(self):
        paths = self._approval()
        rename = xcode_cache.native_rename

        def replace_then_rename(source_fd, source, destination_fd, destination):
            self.cache.rename(self.derived_data / "original-preserved")
            self.cache.mkdir()
            (self.cache / "user.bin").write_bytes(b"Do not purge")
            rename(source_fd, source, destination_fd, destination)

        with patch.object(xcode_cache, "native_rename", side_effect=replace_then_rename):
            result = self._execute(paths)
        self.assertEqual(result["status"], "retained")
        journal = Path(result["journalPath"])
        self.assertEqual((journal.parent / "payload" / "user.bin").read_bytes(), b"Do not purge")
        self.assertTrue((self.derived_data / "original-preserved" / self.cache_relative).exists())

    def test_partial_failure_is_not_reported_as_success_or_full_retention(self):
        paths = self._approval()

        def fail_after_one_file(descriptor, tree):
            os.unlink(self.cache_relative.as_posix(), dir_fd=descriptor)
            raise xcode_cache.AdapterError("Injected failure after one removal")

        with patch.object(xcode_cache, "purge_contents", side_effect=fail_after_one_file):
            result = self._execute(paths)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(Path(result["journalPath"]).exists())

    def test_nested_cache_can_be_removed(self):
        subdirectory = self.cache / "DataStore" / "v5" / "records" / "BB"
        subdirectory.mkdir()
        (subdirectory / "extra.c-0123456789ABC").write_bytes(self.cache_bytes)
        self.assertEqual(self._execute(self._approval())["status"], "removed")

    def test_immutable_journal_survives_failed_outcome_write(self):
        paths = self._approval()
        save = xcode_cache.save_descriptor
        writes = 0

        def interrupted_result(descriptor, value):
            nonlocal writes
            writes += 1
            if writes >= 4:
                raise OSError("Injected outcome write failure")
            return save(descriptor, value)

        with patch.object(xcode_cache, "save_descriptor", side_effect=interrupted_result):
            result = self._execute(paths)
        self.assertEqual(result["status"], "retained")
        self.assertIn("reportError", result)
        journal = next(self.derived_data.glob(".cleanup-staging-*/journal.json"))
        self.assertEqual(json.loads(journal.read_text())["candidateId"], "xcode-index-noindex")
        self.assertEqual(xcode_cache.restore(journal, self.root / "restore.json")["status"], "restored")

    def test_symlink_substitution_during_purge_never_follows_it(self):
        paths = self._approval()
        outside = self.root / "outside.pcm"
        outside.write_bytes(b"Preserve outside")
        purge = xcode_cache.purge_contents

        def substitute(descriptor, tree):
            os.unlink(self.cache_relative.as_posix(), dir_fd=descriptor)
            os.symlink(str(outside), self.cache_relative.as_posix(), dir_fd=descriptor)
            return purge(descriptor, tree)

        with patch.object(xcode_cache, "purge_contents", side_effect=substitute):
            result = self._execute(paths)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(outside.read_bytes(), b"Preserve outside")


class ActivityTests(unittest.TestCase):
    def test_existing_worktree_contracts_still_validate(self):
        schema = json.loads((SCRIPTS.parent / "references" / "audit-manifest.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for fixture in (SCRIPTS.parents[2] / "tests" / "fixtures").glob("*.json"):
            with self.subTest(fixture=fixture.name):
                validator.validate(json.loads(fixture.read_text()))

    def test_busy_empty_or_failed_process_inspection_blocks(self):
        for output, returncode in (("/Applications/Xcode.app/Contents/MacOS/Xcode\n", 0),
                                   ("/usr/bin/swift-frontend\n", 0), ("", 0), ("ps", 1)):
            with self.subTest(output=output), patch.object(xcode_cache.subprocess, "run", return_value=subprocess.CompletedProcess([], returncode, output, "")):
                with self.assertRaises(xcode_cache.AdapterError):
                    xcode_cache.check_activity()

    def test_idle_process_snapshot_is_accepted(self):
        with patch.object(xcode_cache.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "/sbin/launchd\n/usr/bin/python3\n", "")):
            xcode_cache.check_activity()

    def test_execution_on_other_platforms_is_blocked(self):
        with patch.object(xcode_cache.sys, "platform", "linux"):
            with self.assertRaises(xcode_cache.AdapterError):
                xcode_cache.execute(None, None, None, None)


if __name__ == "__main__":
    unittest.main()
