"""Tests for edition-specific release ZIPs."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from build_release import EDITIONS, build_package


class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "source"
        self.root.mkdir()
        for path in (
            "fabrica/__main__.py", "fabrica/__init__.py", "fabrica/web/index.html",
            "docs/guide.md", "README.md", "requirements.txt", "services.json",
            "worker.example.json", "worker.env.example", "CONTRIBUTING.md",
            "PROVIDERS.md", "AGENTS.md.example",
        ):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture", encoding="utf-8")
        (self.root / "fabrica/__pycache__").mkdir()
        (self.root / "fabrica/__pycache__/junk.pyc").write_bytes(b"cache")
        (self.root / ".env").write_text("SECRET=not-for-release", encoding="utf-8")
        (self.root / "profiles").mkdir()
        for _, (_, installer, profile, _) in EDITIONS.items():
            (self.root / installer).write_text("installer", encoding="utf-8")
            (self.root / "profiles" / profile).write_text("{}", encoding="utf-8")

    def test_each_edition_contains_only_its_installer_and_profile(self):
        for edition, (_, installer, profile, _) in EDITIONS.items():
            with self.subTest(edition=edition):
                archive = build_package(self.root, edition, "3.0.1", self.tmp / "out")
                with zipfile.ZipFile(archive) as zf:
                    names = zf.namelist()
                    self.assertTrue(any(name.endswith("/" + installer) for name in names))
                    self.assertTrue(any(name.endswith("/profiles/" + profile) for name in names))
                    profiles = [name for name in names if "/profiles/" in name]
                    self.assertEqual([name.rsplit("/", 1)[-1] for name in profiles], [profile])
                    self.assertFalse(any(name.endswith(".pyc") for name in names))
                    self.assertFalse(any(name.endswith("/.env") for name in names))
                    self.assertFalse(any("worker.token" in name for name in names))

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(ValueError):
            build_package(self.root, "linux-lite", "../main", self.tmp / "out")


if __name__ == "__main__":
    unittest.main()
