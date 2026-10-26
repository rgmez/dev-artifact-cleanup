"""Check the narrow content profile against a real, newly compiled index."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from test_xcode_cache import Fixture, xcode_cache
import validate_execution


@unittest.skipUnless(sys.platform == "darwin", "Representative Apple Clang fixture requires macOS")
class ClangIndexStoreTests(Fixture):
    def test_real_clang_index_is_recognized_then_removed_only_in_fixture(self):
        self._remove_fixture_cache()
        self.cache.mkdir()
        source = self.repository / "fixture.c"
        source.write_text("int cleanup_fixture(void) { return 42; }\n")
        before = source.read_bytes()
        compiler = subprocess.run(["xcrun", "--find", "clang"], capture_output=True, text=True, check=True).stdout.strip()
        compiled = subprocess.run([compiler, "-c", str(source), "-o", str(self.root / "fixture.o"),
                                   "-index-store-path", str(self.cache / "DataStore")], capture_output=True, text=True, timeout=60)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        files = [path for path in self.cache.rglob("*") if path.is_file()]
        self.assertTrue(any("records" in path.parts for path in files))
        self.assertTrue(any("units" in path.parts for path in files))
        self.assertEqual({path.read_bytes()[:4] for path in files}, {b"IDXR", b"IDXU"})
        paths = self._approval()
        manifest = json.loads(paths[0].read_text())
        candidate = manifest["candidates"][0]
        self.assertEqual(candidate["adapter"]["contentProfile"], "indexstore-v5-signature-v1")
        self._validate_schema(manifest)
        result = self._execute(paths)
        self.assertEqual(result["status"], "removed")
        checked = validate_execution.validate_evidence(*paths, Path(result["journalPath"]))
        self.assertTrue(checked["valid"], checked["findings"])
        self.assertTrue(checked["reportedSuccess"])
        self.assertEqual(source.read_bytes(), before)

    def test_real_clang_index_with_manual_notes_is_retained(self):
        self._remove_fixture_cache()
        self.cache.mkdir()
        source = self.repository / "fixture.c"
        source.write_text("int cleanup_fixture(void) { return 42; }\n")
        compiled = subprocess.run(["xcrun", "clang", "-c", str(source), "-o", str(self.root / "fixture.o"),
                                   "-index-store-path", str(self.cache / "DataStore")], capture_output=True, text=True, timeout=60)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        notes = self.cache / "README"
        notes.write_text("Manually authored fixture notes; preserve these bytes.\n")
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in self.cache.rglob("*") if path.is_file()}
        self._requires_review()
        after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in self.cache.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
