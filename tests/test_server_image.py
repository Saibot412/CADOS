"""Exercise the Docker COPY contents without editable-install or desktop fallback."""
import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "Server dependencies required")
class ServerImageTests(unittest.TestCase):
    def test_image_contents_boot_without_desktop_and_seed_database(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)
            for line in (root / "server/Dockerfile").read_text().splitlines():
                parts = shlex.split(line)
                if not parts or parts[0] != "COPY":
                    continue
                source = root / parts[1]
                target = image / parts[2].removeprefix("/app/")
                if source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".env", ".env.*"))
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            site_paths = list({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
            code = '''
import sys, json, asyncio
sys.path[:0] = [sys.argv[1]] + json.loads(sys.argv[2])
class NoDesktop:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'PySide6', 'bleak'} or fullname.startswith('cados.services'):
            raise ImportError('Desktop dependency reached: ' + fullname)
sys.meta_path.insert(0, NoDesktop())
from server.app.main import create_app
from server.app.database import records
import sqlalchemy as sa
app = create_app('sqlite:///' + sys.argv[1] + '/test.sqlite3',
    'http://localhost', bootstrap=('image@example.test', 'image-test-password'))
async def check():
    async with app.router.lifespan_context(app):
        with app.state.engine.connect() as db:
            assert db.execute(sa.select(sa.func.count()).select_from(records)).scalar() == 26
asyncio.run(check())
'''
            result = subprocess.run([sys.executable, "-I", "-S", "-c", code, str(image), json.dumps(site_paths)],
                cwd=image, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
