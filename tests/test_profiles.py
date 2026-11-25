import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def test_all_requested_profiles_exist_and_are_valid_json(self):
        expected = {
            "windows.json", "linux.json",
            "windows-lite.json", "linux-lite.json",
            "windows-heavy.json", "linux-heavy.json",
            "linux-mother.json",
        }
        profiles = ROOT / "profiles"
        self.assertTrue(expected.issubset({p.name for p in profiles.glob("*.json")}))
        for name in expected:
            profile = json.loads((profiles / name).read_text(encoding="utf-8"))
            self.assertIn("edition", profile)
            self.assertIn("role", profile)

    def test_worker_profiles_keep_shell_disabled_by_default(self):
        for path in (ROOT / "profiles").glob("*.json"):
            profile = json.loads(path.read_text(encoding="utf-8"))
            agent = profile.get("agent", {})
            if agent:
                self.assertFalse(agent.get("allow_shell", False), path.name)


if __name__ == "__main__":
    unittest.main()
