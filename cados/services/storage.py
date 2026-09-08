from __future__ import annotations

import json
import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord


def encode(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def workout_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DataStore:
    """Local SQLite storage. No network access or server credentials are used."""

    SCHEMA_VERSION = 1

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > self.SCHEMA_VERSION:
                raise ValueError("Diese Datenbank benötigt eine neuere CADOS-Version.")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user_time ON sessions(user_id, timestamp DESC);
                CREATE TABLE IF NOT EXISTS session_samples (
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    sample_index INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(session_id, sample_index)
                );
                CREATE TABLE IF NOT EXISTS workouts (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL, payload TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE,
                    origin TEXT NOT NULL DEFAULT 'import',
                    revision INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS planned_workouts (
                    id TEXT PRIMARY KEY, date TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS planned_workouts_date ON planned_workouts(date);
                CREATE TABLE IF NOT EXISTS migrations (
                    name TEXT PRIMARY KEY, details TEXT NOT NULL
                );
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5, isolation_level="DEFERRED")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @property
    def status_label(self) -> str:
        return "Speicher: SQLite · lokal"

    def list_profiles(self) -> list[UserProfile]:
        with self.connection() as connection:
            rows = connection.execute("SELECT payload FROM profiles").fetchall()
        return sorted((UserProfile.from_dict(json.loads(row["payload"])) for row in rows),
                      key=lambda profile: profile.name.casefold())

    def save_profile(self, profile: UserProfile) -> None:
        with self.connection() as connection:
            connection.execute("""
                INSERT INTO profiles(id, name, payload) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, payload=excluded.payload
            """, (profile.id, profile.name, encode(profile.to_dict())))

    @staticmethod
    def _save_session(connection: sqlite3.Connection, session: WorkoutSessionRecord) -> None:
        payload = session.to_dict()
        samples = payload.pop("samples")
        connection.execute("""
            INSERT INTO sessions(id, user_id, timestamp, payload) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET user_id=excluded.user_id,
                timestamp=excluded.timestamp, payload=excluded.payload
        """, (session.id, session.user_id, session.timestamp, encode(payload)))
        connection.execute("DELETE FROM session_samples WHERE session_id=?", (session.id,))
        connection.executemany(
            "INSERT INTO session_samples(session_id, sample_index, payload) VALUES (?, ?, ?)",
            ((session.id, index, encode(sample)) for index, sample in enumerate(samples)),
        )

    def save_session(self, session: WorkoutSessionRecord) -> None:
        with self.connection() as connection:
            self._save_session(connection, session)

    def list_sessions(self, user_id: str | None = None, *, include_samples: bool = True) -> list[WorkoutSessionRecord]:
        sql = "SELECT payload FROM sessions"
        parameters: tuple[str, ...] = ()
        if user_id is not None:
            sql += " WHERE user_id=?"
            parameters = (user_id,)
        sql += " ORDER BY timestamp DESC"
        with self.connection() as connection:
            result = []
            for row in connection.execute(sql, parameters).fetchall():
                payload = json.loads(row["payload"])
                if include_samples:
                    payload["samples"] = [json.loads(sample["payload"]) for sample in connection.execute(
                        "SELECT payload FROM session_samples WHERE session_id=? ORDER BY sample_index", (payload["id"],)
                    )]
                result.append(WorkoutSessionRecord.from_dict(payload))
        return result

    def save_plan(self, identifier: str, payload: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute("""
                INSERT INTO planned_workouts(id, date, payload) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET date=excluded.date, payload=excluded.payload
            """, (identifier, str(payload["date"]), encode(payload)))

    def delete_plan(self, identifier: str) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM planned_workouts WHERE id=?", (identifier,))

    def list_plans(self, day: str | None = None) -> list[dict[str, Any]]:
        sql, parameters = "SELECT id, payload FROM planned_workouts", ()
        if day is not None:
            sql += " WHERE date=?"
            parameters = (day,)
        sql += " ORDER BY date, id"
        with self.connection() as connection:
            return [{"id": str(row["id"]), **json.loads(row["payload"])}
                    for row in connection.execute(sql, parameters)]

    def get_workout(self, identifier: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT id, source_name, payload FROM workouts WHERE id=?", (identifier,)).fetchone()
        if row is None:
            return None
        return {"id": str(row["id"]), "source_name": str(row["source_name"]),
                "payload": json.loads(row["payload"])}

    def migration_done(self, name: str) -> bool:
        with self.connection() as connection:
            return connection.execute("SELECT 1 FROM migrations WHERE name=?", (name,)).fetchone() is not None

    @staticmethod
    def _legacy_records(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Die bisherige Datendatei {path.name} ist beschädigt. Sie wurde nicht verändert.") from exc
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise ValueError(f"Ungültiges Datenformat in {path.name}.")
        return payload

    def migrate_legacy_json(self, profiles_path: Path, sessions_path: Path) -> dict[str, int]:
        """Import once, atomically; preserve both original files and newer SQLite rows."""
        name = "legacy_profiles_sessions_v1"
        if self.migration_done(name):
            return {"profiles": 0, "sessions": 0}
        profiles = [UserProfile.from_dict(item) for item in self._legacy_records(profiles_path)]
        sessions = [WorkoutSessionRecord.from_dict(item) for item in self._legacy_records(sessions_path)]
        counts = {"profiles": 0, "sessions": 0}
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM migrations WHERE name=?", (name,)).fetchone():
                return counts
            for profile in profiles:
                cursor = connection.execute("INSERT OR IGNORE INTO profiles(id, name, payload) VALUES (?, ?, ?)",
                                            (profile.id, profile.name, encode(profile.to_dict())))
                counts["profiles"] += cursor.rowcount
            for session in sessions:
                if connection.execute("SELECT 1 FROM sessions WHERE id=?", (session.id,)).fetchone() is None:
                    self._save_session(connection, session)
                    counts["sessions"] += 1
            connection.execute("INSERT INTO migrations(name, details) VALUES (?, ?)", (name, encode(counts)))
        return counts

    def backup(self, destination: Path) -> None:
        if destination.resolve() == self.database_path.resolve():
            raise ValueError("Bitte einen anderen Speicherort für die Sicherung wählen.")
        with self.connection() as connection:
            target = sqlite3.connect(destination)
            try:
                connection.backup(target)
            finally:
                target.close()

    def save_workout(
        self,
        payload: dict[str, Any],
        source_name: str,
        *,
        origin: str = "import",
        workout_id: str | None = None,
        revision: int = 1,
    ) -> str:
        """Insert or update a workout and return its stable local identifier."""
        digest = workout_hash(payload)
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT id FROM workouts WHERE content_hash=?", (digest,)
            ).fetchone()
            if existing is not None:
                return str(existing["id"])

            identifier = workout_id or str(uuid4())
            # A server revision replaces its earlier local copy. A repeated local
            # filename replaces the prior import instead of creating ambiguity.
            by_source = connection.execute(
                "SELECT id FROM workouts WHERE source_name=? COLLATE NOCASE", (source_name,)
            ).fetchone()
            if by_source is not None:
                identifier = str(by_source["id"])

            connection.execute(
                """
                INSERT INTO workouts(id, source_name, name, payload, content_hash, origin, revision)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET source_name=excluded.source_name,
                    name=excluded.name, payload=excluded.payload,
                    content_hash=excluded.content_hash, origin=excluded.origin,
                    revision=excluded.revision
                """,
                (
                    identifier,
                    source_name,
                    str(payload.get("name") or "Workout"),
                    encode(payload),
                    digest,
                    origin,
                    max(1, int(revision)),
                ),
            )
        return identifier

    def list_workouts(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, source_name, payload, origin, revision FROM workouts ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "source_name": str(row["source_name"]),
                "payload": json.loads(row["payload"]),
                "origin": str(row["origin"]),
                "revision": int(row["revision"]),
            }
            for row in rows
        ]
