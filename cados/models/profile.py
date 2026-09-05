from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class UserProfile:
    name: str
    ftp: int
    weight_kg: float | None = None
    max_hr: int | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=iso_now)
    updated_at: str = field(default_factory=iso_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "ftp": self.ftp,
            "weight_kg": self.weight_kg,
            "max_hr": self.max_hr,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @property
    def ftp_watts(self) -> int:
        return self.ftp

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UserProfile":
        ftp_value = payload.get("ftp_watts")
        if ftp_value is None:
            ftp_value = payload.get("ftp")
        max_hr_raw = payload.get("max_hr")
        return cls(
            id=str(payload.get("id") or uuid4()),
            name=str(payload.get("name") or "Standard"),
            ftp=int(ftp_value or 250),
            weight_kg=float(payload["weight_kg"]) if payload.get("weight_kg") is not None else None,
            max_hr=int(max_hr_raw) if max_hr_raw is not None else None,
            created_at=str(payload.get("created_at") or iso_now()),
            updated_at=str(payload.get("updated_at") or iso_now()),
        )
