import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog
from cados.config import AppConfig
from cados.connector_login import ConnectorLogin


class ConnectorLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_success_saves_token_without_password(self):
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig.load(Path(directory))
            dialog = ConnectorLogin(config)
            dialog.email.setText('rider@example.test')
            dialog.password.setText('secret-password')
            with patch('cados.connector_login.WorkoutLibraryClient') as client:
                client.return_value.login.return_value = {'id': 'rider'}
                client.return_value.token = 'session-token'
                client.return_value.base_url = 'https://cados.saibot.at'
                dialog.login()
                dialog.future.result(timeout=2)
                dialog.finish_login()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
            restored = AppConfig.load(Path(directory))
            self.assertEqual(restored.workout_library_token, 'session-token')
            self.assertEqual(restored.current_account['user_id'], 'rider')
            self.assertNotIn('secret-password', restored.paths.settings_path.read_text())

    def test_failed_login_keeps_existing_account(self):
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig.load(Path(directory))
            account = config.remember_account('https://cados.saibot.at', 'old@example.test', token='old')
            config.select_account(account)
            dialog = ConnectorLogin(config)
            dialog.email.setText('new@example.test')
            dialog.password.setText('wrong')
            with patch('cados.connector_login.WorkoutLibraryClient') as client:
                client.return_value.login.side_effect = RuntimeError('Anmeldung fehlgeschlagen')
                dialog.login()
                while not dialog.future.done():
                    time.sleep(.001)
                dialog.finish_login()
            self.assertEqual(config.workout_library_token, 'old')
            self.assertTrue(dialog.submit.isEnabled())
            self.assertIn('fehlgeschlagen', dialog.message.text())
            dialog.reject()
