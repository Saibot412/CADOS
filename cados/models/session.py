from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class WorkoutSessionRecord:
    user_id: str
    user_name: str
    workout_name: str
    duration_sec: int
    status: str
    trainer_source: str
    ftp_test_result: dict[str, Any] | None = None
    plan_id: str | None = None
    perceived_exertion: int | None = None
    workout_file_name: str | None = None
    workout_payload: dict[str, Any] | None = None
    started_at: str | None = None
    ftp_watts: int | None = None
    workout_elapsed_sec: int | None = None
    metrics: dict[str, int | float] = field(default_factory=dict)
    samples: list[dict[str, Any]] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=iso_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ftp_test_result": self.ftp_test_result,
            "plan_id": self.plan_id,
            "perceived_exertion": self.perceived_exertion,
            "started_at": self.started_at,
            "ftp_watts": self.ftp_watts,
            "workout_elapsed_sec": self.workout_elapsed_sec,
            "metrics": self.metrics,
            "samples": self.samples,
            "id": self.id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "workout_name": self.workout_name,
            "workout_file_name": self.workout_file_name,
            "workout_payload": self.workout_payload,
            "duration_sec": self.duration_sec,
            "status": self.status,
            "trainer_source": self.trainer_source,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkoutSessionRecord":
        return cls(
            ftp_test_result=payload.get("ftp_test_result"),
            plan_id=payload.get("plan_id"),
            perceived_exertion=payload.get("perceived_exertion"),
            started_at=payload.get("started_at"),
            ftp_watts=int(payload["ftp_watts"]) if payload.get("ftp_watts") is not None else None,
            workout_elapsed_sec=int(payload["workout_elapsed_sec"]) if payload.get("workout_elapsed_sec") is not None else None,
            metrics=dict(payload.get("metrics") or {}),
            samples=list(payload.get("samples") or []),
            id=str(payload.get("id") or uuid4()),
            timestamp=str(payload.get("timestamp") or iso_now()),
            user_id=str(payload.get("user_id") or ""),
            user_name=str(payload.get("user_name") or "Unbekannt"),
            workout_name=str(payload.get("workout_name") or "Workout"),
            workout_file_name=payload.get("workout_file_name"),
            workout_payload=payload.get("workout_payload"),
            duration_sec=int(payload.get("duration_sec") or 0),
            status=str(payload.get("status") or "unknown"),
            trainer_source=str(payload.get("trainer_source") or "bluetooth_ftms"),
        )
