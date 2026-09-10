"""Download verified release assets; install only after the connector has exited."""
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
import certifi
from cados import __version__


def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+', str(value)):
        raise ValueError('Ungültige Versionsnummer.')
    return tuple(map(int, value.split('.')))


def download_update(base_url, directory):
    if sys.platform != 'darwin':
        raise ValueError('Automatische Installation ist derzeit nur für macOS verfügbar.')
    if urlsplit(base_url).scheme != 'https':
        raise ValueError('Updates benötigen eine HTTPS-Serveradresse.')
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(base_url.rstrip('/') + '/static/connector-release.json', timeout=20, context=context) as response:
        manifest = json.loads(response.read(65536))
    if version(manifest['version']) <= version(__version__):
        raise ValueError('Der Connector ist bereits aktuell.')
    asset = manifest['macos']
    expected_url = 'https://github.com/Saibot412/CADOS/releases/download/v' + manifest['version'] + '/CADOS-Connector-macOS.dmg'
    if asset['url'] != expected_url or not re.fullmatch('[a-f0-9]{64}', asset.get('sha256', '')):
        raise ValueError('Dieses Update besitzt keinen gültigen Download mit Prüfsumme.')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(suffix='.dmg', prefix='cados-', dir=directory)
    digest, length = hashlib.sha256(), 0
    try:
        with os.fdopen(fd, 'wb') as output, urlopen(asset['url'], timeout=30, context=context) as response:
            if urlsplit(response.url).scheme != 'https':
                raise ValueError('Unsicherer Update-Download.')
            while chunk := response.read(1024 * 1024):
                length += len(chunk)
                if length > 500_000_000:
                    raise ValueError('Update-Datei ist zu groß.')
                output.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != asset['sha256']:
            raise ValueError('Prüfsumme stimmt nicht. Update wurde nicht installiert.')
        return {'path': filename, 'version': manifest['version']}
    except Exception:
        Path(filename).unlink(missing_ok=True)
        raise


def launch_installer(update, app_path, pid):
    app_path = Path(app_path).resolve()
    if app_path.suffix != '.app' or not (app_path / 'Contents/Info.plist').is_file():
        raise ValueError('Bitte Updates aus der installierten Connector-App starten.')
    script = Path(__file__).parent / 'assets/local/install-update.sh'
    logfile = Path(update['path']).with_suffix('.log')
    with logfile.open('wb') as output:
        subprocess.Popen(['/bin/sh', str(script), str(pid), update['path'], str(app_path), update['version']],
                         stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
