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
        with patch("cados.config.sys.platform", "darwin"), patch.dict(os.environ, {}, clear=True):
            self.assertTrue(str(user_data_directory()).endswith("Library/Application Support/Cados"))
        with patch("cados.config.sys.platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": "C:/Local"}, clear=True):
            self.assertEqual(str(user_data_directory()), "C:/Local/Cados")

    def test_environment_overrides_server_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "CADOS_LIBRARY_URL": "https://library.example",
            "CADOS_LIBRARY_TOKEN": "environment-token",
        }):
            config = AppConfig.load(Path(directory))
            self.assertEqual(config.workout_library_url, "https://library.example")
            self.assertEqual(config.workout_library_token, "environment-token")
