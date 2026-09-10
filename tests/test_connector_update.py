import hashlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from cados.connector_update import download_update


class Reply(io.BytesIO):
    url = 'https://release-assets.githubusercontent.com/test'


class ConnectorUpdateTests(unittest.TestCase):
    def test_verified_asset_and_corruption_rejection(self):
        asset = b'test dmg bytes'
        manifest = {'version':'99.0.0','macos':{
            'url':'https://github.com/Saibot412/CADOS/releases/download/v99.0.0/CADOS-Connector-macOS.dmg',
            'sha256':hashlib.sha256(asset).hexdigest()}}
        with tempfile.TemporaryDirectory() as directory, patch('cados.connector_update.sys.platform','darwin'):
            with patch('cados.connector_update.urlopen',side_effect=[Reply(json.dumps(manifest).encode()),Reply(asset)]):
                result=download_update('https://cados.saibot.at',directory)
                self.assertEqual(Path(result['path']).read_bytes(),asset)
            count=len(list(Path(directory).iterdir()))
            with patch('cados.connector_update.urlopen',side_effect=[Reply(json.dumps(manifest).encode()),Reply(b'corrupt')]):
                with self.assertRaisesRegex(ValueError,'Prüfsumme'):
                    download_update('https://cados.saibot.at',directory)
            self.assertEqual(len(list(Path(directory).iterdir())),count)
