from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    "tick_interval_ms": 250,
    "trainer_scan_timeout_sec": 5,
    "default_ftp": 250,
    "theme_mode": "light",
    "workout_library_url": "",
    "workout_library_token": "",
}


def user_data_directory() -> Path:
    override = os.getenv("CADOS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Cados"
    if sys.platform == "win32":
        return Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Cados"
    return Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "cados"


@dataclass(slots=True)
class AppPaths:
    root: Path
    assets_dir: Path
    bundled_workouts_dir: Path
    legacy_workouts_dir: Path
    legacy_profiles_path: Path
    legacy_sessions_path: Path
    data_dir: Path
    logs_dir: Path
    settings_path: Path
    database_path: Path
    app_icon_path: Path
    logo_path: Path

    @classmethod
    def for_root(cls, root: Path | None = None, *, data_dir: Path | None = None) -> "AppPaths":
        project_root = (root or Path(__file__).resolve().parents[1]).resolve()
        # Explicit roots isolate tests and development without touching personal data.
        runtime = (data_dir or (project_root / "data" if root is not None else user_data_directory())).resolve()
        assets = project_root / "cados" / "assets"
        return cls(
            root=project_root, assets_dir=assets, bundled_workouts_dir=assets / "workouts",
            legacy_workouts_dir=project_root / "workouts",
            legacy_profiles_path=project_root / "data" / "profiles.json",
            legacy_sessions_path=project_root / "data" / "sessions.json",
            data_dir=runtime, logs_dir=runtime / "logs", settings_path=runtime / "settings.json",
            database_path=runtime / "cados.sqlite3", app_icon_path=assets / "icon.png", logo_path=assets / "logo.png",
        )

    def ensure_runtime_files(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.settings_path.exists():
            settings = dict(DEFAULT_SETTINGS)
            legacy_settings = self.root / "data" / "settings.json"
            if legacy_settings.exists():
                payload = json.loads(legacy_settings.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    settings.update({key: payload[key] for key in DEFAULT_SETTINGS if key in payload})
            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


@dataclass(slots=True)
class AppConfig:
    paths: AppPaths
    tick_interval_ms: int
    trainer_scan_timeout_sec: int
    default_ftp: int
    theme_mode: str
    workout_library_url: str
    workout_library_token: str

    @classmethod
    def load(cls, root: Path | None = None, *, data_dir: Path | None = None) -> "AppConfig":
        paths = AppPaths.for_root(root, data_dir=data_dir)
        paths.ensure_runtime_files()
        settings = dict(DEFAULT_SETTINGS)
        payload = json.loads(paths.settings_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Ungültiges Format der Einstellungen.")
        settings.update(payload)
        return cls(
            paths=paths,
            tick_interval_ms=min(1000, max(100, int(settings["tick_interval_ms"]))),
            trainer_scan_timeout_sec=max(1, int(settings["trainer_scan_timeout_sec"])),
            default_ftp=max(100, int(settings["default_ftp"])),
            theme_mode="light",
            workout_library_url=str(
                os.getenv("CADOS_LIBRARY_URL") or settings["workout_library_url"]
            ).strip(),
            workout_library_token=str(
                os.getenv("CADOS_LIBRARY_TOKEN") or settings["workout_library_token"]
            ).strip(),
        )

    def save_settings(self, updates: dict[str, Any]) -> None:
        settings = json.loads(self.paths.settings_path.read_text(encoding="utf-8"))
        settings.update({key: value for key, value in updates.items() if key in DEFAULT_SETTINGS})
        settings.pop("database_url", None)
        temporary = self.paths.settings_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(self.paths.settings_path)

    def save_theme_mode(self, theme_mode: str) -> None:
        del theme_mode
        self.theme_mode = "light"
        self.save_settings({"theme_mode": "light"})
