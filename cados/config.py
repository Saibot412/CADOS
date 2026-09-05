from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    "database_url": None,
    "tick_interval_ms": 250,
    "trainer_scan_timeout_sec": 5,
    "default_ftp": 250,
    "theme_mode": "light",
}


@dataclass(slots=True)
class AppPaths:
    root: Path
    assets_dir: Path
    workouts_dir: Path
    data_dir: Path
    logs_dir: Path
    settings_path: Path
    profiles_path: Path
    sessions_path: Path
    app_icon_path: Path
    logo_path: Path

    @classmethod
    def for_root(cls, root: Path | None = None) -> "AppPaths":
        project_root = (root or Path(__file__).resolve().parents[1]).resolve()
        data_dir = project_root / "data"
        assets_dir = project_root / "cados" / "assets"
        return cls(
            root=project_root,
            assets_dir=assets_dir,
            workouts_dir=project_root / "workouts",
            data_dir=data_dir,
            logs_dir=project_root / "logs",
            settings_path=data_dir / "settings.json",
            profiles_path=data_dir / "profiles.json",
            sessions_path=data_dir / "sessions.json",
            app_icon_path=assets_dir / "icon.png",
            logo_path=assets_dir / "logo.png",
        )

    def ensure_runtime_files(self) -> None:
        for directory in (self.assets_dir, self.workouts_dir, self.data_dir, self.logs_dir):
            directory.mkdir(parents=True, exist_ok=True)

        if not self.settings_path.exists():
            self.settings_path.write_text(
                json.dumps(DEFAULT_SETTINGS, indent=2),
                encoding="utf-8",
            )

        for json_path in (self.profiles_path, self.sessions_path):
            if not json_path.exists():
                json_path.write_text("[]\n", encoding="utf-8")

        bundled_workout = self.root / "cados_workout_1h.json"
        target_workout = self.workouts_dir / bundled_workout.name
        if bundled_workout.exists() and not target_workout.exists():
            shutil.copy2(bundled_workout, target_workout)


@dataclass(slots=True)
class AppConfig:
    paths: AppPaths
    database_url: str | None
    tick_interval_ms: int
    trainer_scan_timeout_sec: int
    default_ftp: int
    theme_mode: str

    @classmethod
    def load(cls, root: Path | None = None) -> "AppConfig":
        paths = AppPaths.for_root(root)
        paths.ensure_runtime_files()

        settings = dict(DEFAULT_SETTINGS)
        if paths.settings_path.exists():
            try:
                file_settings = json.loads(paths.settings_path.read_text(encoding="utf-8"))
                if isinstance(file_settings, dict):
                    settings.update(file_settings)
            except json.JSONDecodeError:
                pass

        env_database_url = os.getenv("CADOS_DATABASE_URL")
        database_url = env_database_url if env_database_url is not None else settings.get("database_url")

        return cls(
            paths=paths,
            database_url=database_url,
            tick_interval_ms=min(1000, max(100, int(settings.get("tick_interval_ms", 250)))),
            trainer_scan_timeout_sec=max(1, int(settings.get("trainer_scan_timeout_sec", 5))),
            default_ftp=max(100, int(settings.get("default_ftp", 250))),
            theme_mode="light",
        )

    def save_settings(self, updates: dict[str, Any]) -> None:
        settings = dict(DEFAULT_SETTINGS)
        if self.paths.settings_path.exists():
            try:
                payload = json.loads(self.paths.settings_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    settings.update(payload)
            except json.JSONDecodeError:
                pass
        settings.update(updates)
        self.paths.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def save_theme_mode(self, theme_mode: str) -> None:
        del theme_mode
        self.theme_mode = "light"
        self.save_settings({"theme_mode": "light"})
