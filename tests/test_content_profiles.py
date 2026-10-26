"""Portable coverage for the bounded IndexStore content profile."""

from pathlib import Path
import unittest

from test_xcode_cache import Fixture, xcode_cache


class ContentProfileTests(Fixture):
    def _candidate(self, name="Index.noindex"):
        return next(item for item in self._audit()["candidates"] if Path(item["path"]).name == name)

    def _assert_review_and_preserved(self, path, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        candidate = self._candidate()
        self.assertEqual(candidate["risk"], "requires-review")
        self.assertEqual(candidate["auditRecommendation"], "requires-review")
        self.assertEqual(path.read_bytes(), contents)

    def _remove_unknown_entry(self, path):
        path.unlink()
        for parent in path.parents:
            if parent == self.cache:
                break
            try:
                parent.rmdir()
            except OSError:
                break

    def test_manual_and_unknown_root_entries_require_review(self):
        for name, contents in (("README", b"read me"), ("notes.rtf", b"notes"), ("unknown.dat", b"data"), ("cache.pcm", b"pcm")):
            with self.subTest(name=name):
                self._assert_review_and_preserved(self.cache / name, contents)
                (self.cache / name).unlink()

    def test_valid_path_with_wrong_signature_requires_review(self):
        path = self.cache / self.cache_relative
        self._assert_review_and_preserved(path, b"IDXU\x01\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00")

    def test_truncated_header_and_incompatible_lengths_require_review(self):
        path = self.cache / self.cache_relative
        for contents in (b"IDXR", b"IDXR\x01\x08\x00\x00\x01\x00\x00\x00", b"IDXR\x01\x08\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00"):
            with self.subTest(contents=contents):
                self._assert_review_and_preserved(path, contents)
                path.unlink()

    def test_unknown_version_and_arbitrary_directories_require_review(self):
        path = self.cache / "DataStore" / "v6" / "records" / "AA" / "fixture-01234567"
        self._assert_review_and_preserved(path, self.cache_bytes)
        self._remove_unknown_entry(path)
        for relative in ("DataStore/v5/random/AA/file-01234567", "random/AA/file-01234567"):
            candidate_path = self.cache / relative
            self._assert_review_and_preserved(candidate_path, self.cache_bytes)
            self._remove_unknown_entry(candidate_path)

    def test_empty_allowlisted_caches_are_eligible_with_empty_profile(self):
        self._remove_fixture_cache()
        for name in xcode_cache.CACHES:
            (self.derived_data / name).mkdir()
        manifest = self._audit()
        for candidate in manifest["candidates"]:
            self.assertEqual(candidate["risk"], "safe-candidate")
            self.assertEqual(candidate["auditRecommendation"], "eligible-for-execution")
            self.assertEqual(candidate["adapter"]["contentProfile"], "empty-cache-v1")

    def test_filled_non_index_caches_require_review_without_adapter(self):
        self._remove_fixture_cache()
        for name in xcode_cache.CACHES:
            cache = self.derived_data / name
            cache.mkdir()
            (cache / "fixture.bin").write_bytes(b"binary fixture")
        manifest = self._audit()
        for candidate in manifest["candidates"]:
            self.assertEqual(candidate["risk"], "requires-review")
            self.assertEqual(candidate["auditRecommendation"], "requires-review")
            self.assertIsNone(candidate["adapter"])

    def test_crossed_record_and_unit_signatures_require_review(self):
        records = self.cache / "DataStore/v5/records/AA/fixture-01234567"
        units = self.cache / "DataStore/v5/units/fixture-01234567"
        self._assert_review_and_preserved(records, b"IDXU\x01\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00")
        records.unlink()
        self._assert_review_and_preserved(units, b"IDXR\x01\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00")

    def test_valid_unit_signature_uses_indexstore_profile(self):
        self._remove_fixture_cache()
        path = self.cache / "DataStore/v5/units/fixture-ABCDEF12"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"IDXU\x01\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00")
        candidate = self._candidate()
        self.assertEqual(candidate["risk"], "safe-candidate")
        self.assertEqual(candidate["adapter"]["contentProfile"], "indexstore-v5-signature-v1")
        self.assertEqual(path.read_bytes(), b"IDXU\x01\x08\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00")


if __name__ == "__main__":
    unittest.main()
