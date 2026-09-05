from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord
from cados.models.workout import WorkoutTemplate
from cados.services.postgres import PostgresMirror

logger = logging.getLogger(__name__)


class LocalJsonStore:
    def __init__(self, profiles_path: Path, sessions_path: Path):
        self.profiles_path = profiles_path
        self.sessions_path = sessions_path

    def _read_json_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise ValueError(f"Beschädigte Datendatei: {path}. Die Datei wurde nicht verändert.") from None
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise ValueError(f"Ungültiges Datenformat in {path}.")
        return payload

    def _write_json_list(self, path: Path, payload: list[dict[str, Any]]) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def list_profiles(self) -> list[UserProfile]:
        profiles = [UserProfile.from_dict(item) for item in self._read_json_list(self.profiles_path)]
        return sorted(profiles, key=lambda profile: profile.name.lower())

    def save_profile(self, profile: UserProfile) -> None:
        profiles = self.list_profiles()
        by_id = {existing.id: existing for existing in profiles}
        by_id[profile.id] = profile
        self._write_json_list(
            self.profiles_path,
            [item.to_dict() for item in sorted(by_id.values(), key=lambda value: value.name.lower())],
        )

    def list_sessions(self, user_id: str | None = None) -> list[WorkoutSessionRecord]:
        sessions = [WorkoutSessionRecord.from_dict(item) for item in self._read_json_list(self.sessions_path)]
        if user_id:
            sessions = [session for session in sessions if session.user_id == user_id]
        return sorted(sessions, key=lambda session: session.timestamp, reverse=True)

    def save_session(self, session: WorkoutSessionRecord) -> None:
        sessions = self.list_sessions()
        by_id = {existing.id: existing for existing in sessions}
        by_id[session.id] = session
        ordered = sorted(by_id.values(), key=lambda value: value.timestamp, reverse=True)
        self._write_json_list(self.sessions_path, [item.to_dict() for item in ordered])


class DataStore:
    def __init__(self, profiles_path: Path, sessions_path: Path, database_url: str | None):
        self.local = LocalJsonStore(profiles_path, sessions_path)
        self.postgres = PostgresMirror(database_url)

    def _mirror_call(self, action: Callable[..., Any], *args: Any, fallback: Any = None) -> Any:
        try:
            return action(*args)
        except Exception:
            logger.exception("Postgres-Spiegelung fehlgeschlagen; lokale Daten bleiben erhalten.")
            return fallback

    @property
    def status_label(self) -> str:
        if self.postgres.enabled:
            return "Speicher: lokal + Postgres"
        return "Speicher: lokal"

    def list_profiles(self) -> list[UserProfile]:
        profiles = self.local.list_profiles()
        if profiles:
            for profile in profiles:
                self._mirror_call(self.postgres.save_profile, profile)
            return profiles

        remote_profiles = self._mirror_call(self.postgres.list_profiles, fallback=[])
        for profile in remote_profiles:
            self.local.save_profile(profile)
        return remote_profiles

    def save_profile(self, profile: UserProfile) -> None:
        self.local.save_profile(profile)
        self._mirror_call(self.postgres.save_profile, profile)

    def list_sessions(self, user_id: str | None = None) -> list[WorkoutSessionRecord]:
        sessions = self.local.list_sessions(user_id)
        if sessions:
            for session in sessions:
                self._mirror_call(self.postgres.save_session, session)
            return sessions

        remote_sessions = self._mirror_call(self.postgres.list_sessions, user_id, fallback=[])
        for session in remote_sessions:
            self.local.save_session(session)
        return remote_sessions

    def save_session(self, session: WorkoutSessionRecord, workout: WorkoutTemplate | None = None) -> None:
        self.local.save_session(session)
        self._mirror_call(self.postgres.save_session, session, workout)

    def sync_workout(self, workout: WorkoutTemplate) -> None:
        self._mirror_call(self.postgres.sync_workout, workout)
