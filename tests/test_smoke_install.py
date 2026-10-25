import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "smoke_install.py"
SPEC = importlib.util.spec_from_file_location("cleanup_smoke_install", SOURCE)
smoke_install = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke_install)


class PackageResourceTests(unittest.TestCase):
    def test_generated_bytecode_is_not_a_required_install_resource(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resources = ["SKILL.md", "LICENSE.txt", "references/contract.json", "scripts/adapter.py",
                         "scripts/__pycache__/adapter.cpython-312.pyc", "scripts/legacy.pyc", "scripts/legacy.pyo"]
            for relative in resources:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"Synthetic packaging fixture")
            actual = {path.relative_to(root).as_posix() for path in smoke_install.package_resources(root)}
            self.assertEqual(actual, set(resources[:4]))

    def test_new_source_scripts_and_hidden_config_are_not_silently_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("untracked-helper.py", ".required-config"):
                (root / name).write_bytes(b"Required fixture")
            self.assertEqual({path.name for path in smoke_install.package_resources(root)},
                             {"untracked-helper.py", ".required-config"})


if __name__ == "__main__":
    unittest.main()
