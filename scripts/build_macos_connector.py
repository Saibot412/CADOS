"""Build the installable CADOS Connector DMG on macOS.

Run on a Mac with the project virtual environment active.  The resulting DMG
is kept out of Git and uploaded as an asset to the matching GitHub release.
The web release manifest points users to that download.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True, env={
        **os.environ, "PYINSTALLER_CONFIG_DIR": str(ROOT / "build" / ".pyinstaller"),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "release")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("Eine macOS-DMG kann nur auf einem Mac gebaut werden.")

    build, dist = ROOT / "build" / "connector", ROOT / "dist" / "connector"
    shutil.rmtree(build, ignore_errors=True)
    shutil.rmtree(dist, ignore_errors=True)
    entry = build / "connector_entry.py"
    build.mkdir(parents=True)
    entry.write_text("from cados.connector_app import run\nraise SystemExit(run())\n", encoding="utf-8")
    run(
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "CADOS Connector", "--osx-bundle-identifier", "local.cados.connector",
        "--add-data", str(ROOT / "cados" / "assets") + ":cados/assets", "--distpath", str(dist),
        "--workpath", str(build / "work"), "--specpath", str(build), str(entry),
    )
    app = dist / "CADOS Connector.app"
    if not app.exists():
        raise RuntimeError("PyInstaller hat keine Connector-App erstellt.")
    plist = app / "Contents" / "Info.plist"
    for key, value in (
        ("NSBluetoothAlwaysUsageDescription", "CADOS Connector verbindet sich per Bluetooth mit deinem Smart Trainer und Herzfrequenzsensor."),
        ("NSBluetoothPeripheralUsageDescription", "CADOS Connector verbindet sich per Bluetooth mit deinem Smart Trainer und Herzfrequenzsensor."),
    ):
        run("/usr/libexec/PlistBuddy", "-c", f"Add :{key} string {value}", str(plist))
    with plist.open('rb') as handle:
        info = plistlib.load(handle)
    from cados import __version__
    info['CFBundleShortVersionString'] = __version__
    info['CFBundleVersion'] = __version__
    info['CFBundleURLTypes'] = [{
        'CFBundleURLName': 'local.cados.connector',
        'CFBundleURLSchemes': ['cados-connector'],
        'CFBundleTypeRole': 'Viewer',
    }]
    with plist.open('wb') as handle:
        plistlib.dump(info, handle)
    run("codesign", "--force", "--deep", "--sign", "-", str(app))
    args.output.mkdir(parents=True, exist_ok=True)
    dmg = args.output / "CADOS-Connector-macOS.dmg"
    if dmg.exists():
        dmg.unlink()
    staging = build / 'dmg'
    staging.mkdir()
    shutil.copytree(app, staging / app.name, symlinks=True)
    (staging / 'Programme').symlink_to('/Applications')
    (staging / 'Installation.txt').write_text(
        'CADOS Connector installieren\n\n'
        '1. CADOS Connector.app auf Programme ziehen.\n'
        '2. App aus Programme öffnen.\n'
        '3. Falls macOS blockiert: Systemeinstellungen > Datenschutz & Sicherheit > Dennoch öffnen.\n'
        '   Diese App ist nicht von Apple notarisiert.\n'
        '4. Bluetooth erlauben und das Konto im Browser bestätigen.\n'
        '5. Updates über das Connector-Fenster installieren (außerhalb eines Trainings).\n', encoding='utf-8')
    run("hdiutil", "create", "-volname", "CADOS Connector", "-srcfolder", str(staging),
        "-ov", "-format", "UDZO", "-imagekey", "zlib-level=9", str(dmg))
    manifest_path = ROOT / 'server/app/static/connector-release.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['version'] = __version__
    manifest['macos'] = {'url': f'https://github.com/Saibot412/CADOS/releases/download/v{__version__}/CADOS-Connector-macOS.dmg',
                         'sha256': hashlib.sha256(dmg.read_bytes()).hexdigest()}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(dmg)


if __name__ == "__main__":
    main()
