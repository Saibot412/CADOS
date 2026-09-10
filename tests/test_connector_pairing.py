import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from cados.config import AppConfig
from cados.connector_pairing import ConnectorPairing


class ConnectorPairingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_browser_approval_saves_account_without_password(self):
        with tempfile.TemporaryDirectory() as directory:
            config = AppConfig.load(Path(directory))
            dialog = ConnectorPairing(config)
            with patch('cados.connector_pairing.WorkoutLibraryClient') as client, patch('cados.connector_pairing.QDesktopServices.openUrl') as opened:
                client.return_value.base_url = 'https://cados.saibot.at'
                client.return_value._request.side_effect = [
                    {'secret':'test-secret','code':'test-code','url':'https://cados.saibot.at/?pair=test-code'},
                    {'token':'test-token','user':{'email':'test@example.test','id':'test-user'}}]
                dialog.begin()
                dialog.future.result(timeout=2)
                dialog.poll()
                opened.assert_called_once()
                self.assertEqual(config.workout_library_token, '')
                dialog.next_poll = 0
                dialog.poll()
                dialog.future.result(timeout=2)
                dialog.poll()
            restored = AppConfig.load(Path(directory))
            self.assertEqual(restored.current_account['user_id'], 'test-user')
            self.assertEqual(restored.workout_library_token, 'test-token')
            self.assertNotIn('password', restored.paths.settings_path.read_text())
