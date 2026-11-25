import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fabrica.setup import _write_provider_secret
from fabrica.config import _parse_dotenv


class SetupSecretTests(unittest.TestCase):
    def test_provider_key_is_collected_without_echo_and_saved_locally(self):
        home = Path(tempfile.mkdtemp())
        config = home / "worker.json"
        config.write_text("{}", encoding="utf-8")
        with patch("fabrica.setup.getpass.getpass", return_value="test-key-123") as prompt:
            _write_provider_secret({"id": "test", "api_key_env": "TEST_PROVIDER_KEY"}, config)
        prompt.assert_called_once()
        env_path = home / ".worker.env"
        self.assertEqual(_parse_dotenv(env_path)["TEST_PROVIDER_KEY"], "test-key-123")
        if __import__("os").name != "nt":
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_provider_key_can_be_deferred_without_overwriting_other_keys(self):
        home = Path(tempfile.mkdtemp())
        config = home / "worker.json"
        config.write_text("{}", encoding="utf-8")
        env_path = home / ".worker.env"
        env_path.write_text("EXISTING_KEY=keep-me\n", encoding="utf-8")
        with patch("fabrica.setup.getpass.getpass", return_value=""):
            _write_provider_secret({"id": "test", "api_key_env": "TEST_PROVIDER_KEY"}, config)
        loaded = _parse_dotenv(env_path)
        self.assertEqual(loaded["EXISTING_KEY"], "keep-me")
        self.assertEqual(loaded["TEST_PROVIDER_KEY"], "PEGAR_CLAVE_LOCALMENTE")


if __name__ == "__main__":
    unittest.main()
