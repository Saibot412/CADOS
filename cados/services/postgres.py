from __future__ import annotations

import logging
from typing import Any

from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord
from cados.models.workout import WorkoutTemplate

logger = logging.getLogger(__name__)

try:
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
except ImportError:  # pragma: no cover - optional dependency at runtime
    sa = None
    JSONB = None
    pg_insert = None


class PostgresMirror:
    def __init__(self, database_url: str | None):
        self.database_url = database_url
        self._engine: Any | None = None
        self._metadata: Any | None = None
        self._profiles_table: Any | None = None
        self._workouts_table: Any | None = None
        self._sessions_table: Any | None = None
        self._ready = False
        self._disabled_reason: str | None = None

    @property
    def enabled(self) -> bool:
        return self._ensure_ready()

    @property
    def status_label(self) -> str:
        if self._ensure_ready():
            return "Postgres aktiv"
        if self._disabled_reason:
            return f"Postgres inaktiv: {self._disabled_reason}"
        return "Postgres deaktiviert"

    def _ensure_ready(self) -> bool:
        if self._ready:
            return True

        if not self.database_url:
            self._disabled_reason = "keine URL konfiguriert"
            return False
        if sa is None or JSONB is None or pg_insert is None:
            self._disabled_reason = "SQLAlchemy oder psycopg fehlt"
            return False
        if not self.database_url.startswith("postgresql"):
            self._disabled_reason = "nur PostgreSQL wird unterstuetzt"
            return False

        try:
            self._engine = sa.create_engine(self.database_url, pool_pre_ping=True)
            self._metadata = sa.MetaData()

            self._profiles_table = sa.Table(
                "profiles",
                self._metadata,
                sa.Column("id", sa.String(64), primary_key=True),
                sa.Column("name", sa.String(255), nullable=False),
                sa.Column("ftp", sa.Integer, nullable=False),
                sa.Column("weight_kg", sa.Float, nullable=True),
                sa.Column("max_hr", sa.Integer, nullable=True),
                sa.Column("created_at", sa.String(64), nullable=False),
                sa.Column("updated_at", sa.String(64), nullable=False),
            )
            self._workouts_table = sa.Table(
                "workouts",
                self._metadata,
                sa.Column("id", sa.String(255), primary_key=True),
                sa.Column("source_name", sa.String(255), nullable=False, unique=True),
                sa.Column("name", sa.String(255), nullable=False),
                sa.Column("payload", JSONB, nullable=False),
                sa.Column("updated_at", sa.BigInteger, nullable=False),
            )
            self._sessions_table = sa.Table(
                "sessions",
                self._metadata,
                sa.Column("id", sa.String(64), primary_key=True),
                sa.Column("timestamp", sa.String(64), nullable=False),
                sa.Column("user_id", sa.String(64), nullable=False),
                sa.Column("user_name", sa.String(255), nullable=False),
                sa.Column("workout_name", sa.String(255), nullable=False),
                sa.Column("workout_file_name", sa.String(255), nullable=True),
                sa.Column("workout_payload", JSONB, nullable=True),
                sa.Column("duration_sec", sa.Integer, nullable=False),
                sa.Column("status", sa.String(64), nullable=False),
                sa.Column("trainer_source", sa.String(64), nullable=False),
                sa.Column("started_at", sa.String(64), nullable=True),
                sa.Column("ftp_watts", sa.Integer, nullable=True),
                sa.Column("workout_elapsed_sec", sa.Integer, nullable=True),
                sa.Column("metrics", JSONB, nullable=True),
                sa.Column("samples", JSONB, nullable=True),
            )
            self._metadata.create_all(self._engine)
            self._migrate_add_columns(self._engine)
            self._ready = True
            logger.info("PostgreSQL-Mirror aktiviert.")
            return True
        except Exception as exc:  # pragma: no cover - depends on runtime DB
            self._disabled_reason = str(exc)
            logger.warning("PostgreSQL-Mirror konnte nicht initialisiert werden: %s", exc)
            return False

    @staticmethod
    def _migrate_add_columns(engine: sa.Engine) -> None:
        """Add columns that may be missing from older schemas."""
        migrations = [
            ("profiles", "max_hr", "INTEGER"),
            ("sessions", "started_at", "VARCHAR(64)"),
            ("sessions", "ftp_watts", "INTEGER"),
            ("sessions", "workout_elapsed_sec", "INTEGER"),
            ("sessions", "metrics", "JSONB"),
            ("sessions", "samples", "JSONB"),
        ]
        with engine.begin() as conn:
            for table, column, col_type in migrations:
                conn.execute(sa.text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}"
                ))

    def list_profiles(self) -> list[UserProfile]:
        if not self._ensure_ready():
            return []
        statement = sa.select(self._profiles_table).order_by(self._profiles_table.c.name.asc())
        with self._engine.begin() as connection:
            rows = connection.execute(statement).mappings().all()
        return [UserProfile.from_dict(dict(row)) for row in rows]

    def save_profile(self, profile: UserProfile) -> None:
        if not self._ensure_ready():
            return
        values = profile.to_dict()
        statement = pg_insert(self._profiles_table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[self._profiles_table.c.id],
            set_=values,
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def sync_workout(self, workout: WorkoutTemplate) -> None:
        if not self._ensure_ready():
            return
        values = {
            "id": workout.source_path.name,
            "source_name": workout.source_path.name,
            "name": workout.name,
            "payload": workout.to_dict(),
            "updated_at": workout.source_path.stat().st_mtime_ns if workout.source_path.exists() else 0,
        }
        statement = pg_insert(self._workouts_table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[self._workouts_table.c.id],
            set_=values,
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def list_sessions(self, user_id: str | None = None) -> list[WorkoutSessionRecord]:
        if not self._ensure_ready():
            return []
        statement = sa.select(self._sessions_table).order_by(self._sessions_table.c.timestamp.desc())
        if user_id:
            statement = statement.where(self._sessions_table.c.user_id == user_id)
        with self._engine.begin() as connection:
            rows = connection.execute(statement).mappings().all()
        return [WorkoutSessionRecord.from_dict(dict(row)) for row in rows]

    def save_session(self, session: WorkoutSessionRecord, workout: WorkoutTemplate | None = None) -> None:
        if not self._ensure_ready():
            return
        if workout is not None:
            self.sync_workout(workout)
        values = session.to_dict()
        statement = pg_insert(self._sessions_table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[self._sessions_table.c.id],
            set_=values,
        )
        with self._engine.begin() as connection:
            connection.execute(statement)
