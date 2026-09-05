from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import JSONB

from server.app.validation import validate_source_name, validate_workout_payload


DATABASE_URL = os.environ.get("DATABASE_URL", "")
LIBRARY_TOKEN = os.environ.get("CADOS_LIBRARY_TOKEN", "")
if not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
    raise RuntimeError("DATABASE_URL must point to PostgreSQL")
if len(LIBRARY_TOKEN) < 24:
    raise RuntimeError("CADOS_LIBRARY_TOKEN must contain at least 24 characters")

engine = sa.create_engine(DATABASE_URL, pool_pre_ping=True)
metadata = sa.MetaData()
workouts = sa.Table(
    "cados_workout_library",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("source_name", sa.String(255), nullable=False, unique=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("payload", JSONB, nullable=False),
    sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
    sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


class WorkoutUpload(BaseModel):
    source_name: str
    payload: dict


def authorize(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {LIBRARY_TOKEN}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


def serialize(row: sa.RowMapping) -> dict:
    return {
        "id": row["id"],
        "source_name": row["source_name"],
        "revision": row["revision"],
        "payload": row["payload"],
        "updated_at": row["updated_at"].isoformat(),
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    metadata.create_all(engine)
    yield
    engine.dispose()


app = FastAPI(title="CADOS Workout Library", version="1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(sa.text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/v1/workouts", dependencies=[Depends(authorize)])
def list_workouts() -> dict[str, list[dict]]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(workouts).order_by(workouts.c.name.asc())
        ).mappings().all()
    return {"workouts": [serialize(row) for row in rows]}


@app.post("/api/v1/workouts", dependencies=[Depends(authorize)])
def save_workout(upload: WorkoutUpload) -> dict:
    try:
        source_name = validate_source_name(upload.source_name)
        payload = validate_workout_payload(upload.payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    canonical = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    now = datetime.now(tz=UTC)
    with engine.begin() as connection:
        existing_hash = connection.execute(
            sa.select(workouts).where(workouts.c.content_hash == digest)
        ).mappings().first()
        if existing_hash is not None:
            return serialize(existing_hash)
        existing = connection.execute(
            sa.select(workouts).where(workouts.c.source_name == source_name)
        ).mappings().first()
        if existing is None:
            identifier = str(uuid4())
            revision = 1
            connection.execute(workouts.insert().values(
                id=identifier, source_name=source_name, name=payload["name"],
                payload=payload, content_hash=digest, revision=revision, updated_at=now,
            ))
        else:
            identifier = existing["id"]
            revision = int(existing["revision"]) + 1
            connection.execute(workouts.update().where(workouts.c.id == identifier).values(
                name=payload["name"], payload=payload, content_hash=digest,
                revision=revision, updated_at=now,
            ))
        row = connection.execute(
            sa.select(workouts).where(workouts.c.id == identifier)
        ).mappings().one()
    return serialize(row)


@app.delete("/api/v1/workouts/{workout_id}", dependencies=[Depends(authorize)])
def delete_workout(workout_id: str) -> Response:
    with engine.begin() as connection:
        result = connection.execute(workouts.delete().where(workouts.c.id == workout_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="workout not found")
    return Response(status_code=204)
