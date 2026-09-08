"""Build the installable CADOS Connector DMG on macOS.

Run on a Mac with the project virtual environment active.  The resulting DMG
is intentionally kept out of Git and can be copied to the server's static
downloads directory after it has been code-signed and notarized.
"""
from __future__ import annotations

import argparse
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
    run("hdiutil", "create", "-volname", "CADOS Connector", "-srcfolder", str(app),
        "-ov", "-format", "UDZO", "-imagekey", "zlib-level=9", str(dmg))
    print(dmg)


if __name__ == "__main__":
    main()
