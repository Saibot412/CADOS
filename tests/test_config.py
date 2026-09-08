import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cados.config import AppConfig, user_data_directory


class ConfigTests(unittest.TestCase):
    def test_explicit_root_uses_isolated_test_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = AppConfig.load(root)
            self.assertEqual(config.paths.data_dir, (root / "data").resolve())
            self.assertEqual(config.paths.database_path, (root / "data" / "cados.sqlite3").resolve())

    def test_platform_data_paths(self):
        home = Path(tempfile.gettempdir()) / "cados-test-user"
        with patch("cados.config.sys.platform", "darwin"), patch.dict(os.environ, {}, clear=True), \
                patch("cados.config.Path.home", return_value=home):
            self.assertEqual(user_data_directory(), home / "Library" / "Application Support" / "Cados")
        with patch("cados.config.sys.platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": "C:/Local"}, clear=True):
            self.assertEqual(user_data_directory(), Path("C:/Local") / "Cados")

    def test_environment_overrides_server_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "CADOS_LIBRARY_URL": "https://library.example",
            "CADOS_LIBRARY_TOKEN": "environment-token",
        }):
            config = AppConfig.load(Path(directory))
            self.assertEqual(config.workout_library_url, "https://library.example")
            self.assertEqual(config.workout_library_token, "environment-token")

    def test_known_account_is_kept_without_storing_a_password(self):
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig.load(Path(directory))
            config.remember_account("https://cados.saibot.at/", "rider@example.test")
            restored = AppConfig.load(Path(directory))
            self.assertEqual(restored.known_accounts, [{"url": "https://cados.saibot.at", "email": "rider@example.test"}])
            self.assertNotIn("password", restored.paths.settings_path.read_text())
