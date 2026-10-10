import json
import shutil
import sys
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.package_release import RELEASE_FILES, build_release
from tools.validate_skill import validate


class PackagingTests(unittest.TestCase):
    def test_skill_metadata_references_and_assets(self):
        result = validate()
        self.assertTrue(result["ok"])
        self.assertEqual(result["name"], "daymirror")
        self.assertTrue(result["json_assets_valid"])
        self.assertTrue(result["citation_metadata_consistent"])

    def test_private_canaries_are_excluded_by_allowlist(self):
        work = (ROOT / "work" / "tests").resolve()
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        target = Path(temporary.name).resolve()
        self.assertTrue(target.is_relative_to(work))
        try:
            for name in RELEASE_FILES:
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, path)
            canary = uuid.uuid4().hex
            for name in ("private/workspace/journals/secret.md", "work/secret.json", "unknown-notes.md",
                         "daymirror/assets/real-journal.md", "daymirror/scripts/daymirror_core/private-notes.py"):
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(canary, encoding="utf-8")
            result = build_release(target)
            with zipfile.ZipFile(result["archive"]) as archive:
                self.assertEqual(set(archive.namelist()), set(RELEASE_FILES))
                self.assertEqual(archive.read("CITATION.cff"), archive.read("daymirror/CITATION.cff"))
                self.assertEqual(archive.read("LICENSE"), archive.read("daymirror/LICENSE"))
                self.assertIn(b"Arsen1668", archive.read("daymirror/LICENSE"))
                self.assertIn("daymirror/references/provenance.md", archive.namelist())
                for name in archive.namelist():
                    self.assertNotIn(canary.encode(), archive.read(name))
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["policy"], "fixed_allowlist")
            self.assertFalse(manifest["private_directories_included"])
        finally:
            if not target.is_relative_to(work):
                raise RuntimeError("Unsafe cleanup target")
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
