from __future__ import annotations

import json
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    "trainer_scan_timeout_sec": 5,
    "workout_library_url": "",
    "workout_library_token": "",
    "known_accounts": [],
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
            database_path=runtime / "cados.sqlite3", app_icon_path=assets / "icon.png",
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
    trainer_scan_timeout_sec: int
    workout_library_url: str
    workout_library_token: str
    known_accounts: list[dict[str, str]]

    @classmethod
    def load(cls, root: Path | None = None, *, data_dir: Path | None = None) -> "AppConfig":
        paths = AppPaths.for_root(root, data_dir=data_dir)
        paths.ensure_runtime_files()
        settings = dict(DEFAULT_SETTINGS)
        payload = json.loads(paths.settings_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Ungültiges Format der Einstellungen.")
        settings.update(payload)
        known_accounts: list[dict[str, str]] = []
        for account in settings["known_accounts"] if isinstance(settings["known_accounts"], list) else []:
            if not isinstance(account, dict):
                continue
            email, url = str(account.get("email", "")).strip(), str(account.get("url", "")).strip().rstrip("/")
            if email and url:
                known_accounts.append({
                    "email": email,
                    "url": url,
                    "token": str(account.get("token", "")).strip(),
                    "user_id": str(account.get("user_id", "")).strip(),
                    "data_file": str(account.get("data_file", "")).strip(),
                })
        current_url = str(os.getenv("CADOS_LIBRARY_URL") or settings["workout_library_url"]).strip().rstrip("/")
        current_token = str(os.getenv("CADOS_LIBRARY_TOKEN") or settings["workout_library_token"]).strip()
        if current_url and current_token:
            for account in known_accounts:
                if account["url"] == current_url:
                    account["token"] = account["token"] or current_token
                    break
        return cls(
            paths=paths,
            trainer_scan_timeout_sec=max(1, int(settings["trainer_scan_timeout_sec"])),
            workout_library_url=current_url,
            workout_library_token=current_token,
            known_accounts=known_accounts,
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

    @property
    def active_accounts(self) -> list[dict[str, str]]:
        return [account for account in self.known_accounts if account.get("token")]

    @property
    def current_account(self) -> dict[str, str] | None:
        return next((account for account in self.active_accounts
                     if account["url"] == self.workout_library_url
                     and account["token"] == self.workout_library_token), None)

    def remember_account(
        self, url: str, email: str, *, token: str = "", user_id: str = ""
    ) -> dict[str, str]:
        normalized_url, normalized_email = url.strip().rstrip("/"), email.strip()
        existing = next((item for item in self.known_accounts
                         if item["url"] == normalized_url and item["email"] == normalized_email), None)
        if existing:
            data_file = existing.get("data_file", "")
            token = token or existing.get("token", "")
            user_id = user_id or existing.get("user_id", "")
        else:
            key_source = f"{normalized_url}\0{user_id or normalized_email}".encode("utf-8")
            key = hashlib.sha256(key_source).hexdigest()[:20]
            data_file = "" if not self.known_accounts else f"accounts/{key}/cados.sqlite3"
        account = {
            "url": normalized_url,
            "email": normalized_email,
            "token": token.strip(),
            "user_id": user_id.strip(),
            "data_file": data_file,
        }
        if not account["url"] or not account["email"]:
            return account
        self.known_accounts = [item for item in self.known_accounts
                               if not (item["url"] == account["url"] and item["email"] == account["email"])]
        self.known_accounts.insert(0, account)
        self.known_accounts = self.known_accounts[:10]
        self.save_settings({"known_accounts": self.known_accounts})
        return account

    def select_account(self, account: dict[str, str]) -> None:
        self.workout_library_url = account.get("url", "")
        self.workout_library_token = account.get("token", "")
        self.save_settings({
            "workout_library_url": self.workout_library_url,
            "workout_library_token": self.workout_library_token,
        })

    def deactivate_account(self, url: str, email: str) -> None:
        for account in self.known_accounts:
            if account["url"] == url.rstrip("/") and account["email"] == email:
                account["token"] = ""
        self.workout_library_url = ""
        self.workout_library_token = ""
        self.save_settings({
            "known_accounts": self.known_accounts,
            "workout_library_url": "",
            "workout_library_token": "",
        })

    def database_path_for_account(self, account: dict[str, str]) -> Path:
        relative = account.get("data_file", "").strip()
        if not relative:
            return self.paths.database_path
        candidate = (self.paths.data_dir / relative).resolve()
        if self.paths.data_dir not in candidate.parents:
            raise ValueError("Ungültiger Kontodatenpfad.")
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate
