from __future__ import annotations

import json
import math
from pathlib import PurePath
from typing import Any


def validate_workout_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        raise ValueError("workout name is required")
    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks or len(blocks) > 2_000:
        raise ValueError("workout needs between 1 and 2000 blocks")
    total_duration = 0
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") not in {"steady", "ramp"}:
            raise ValueError("unsupported workout block")
        duration = block.get("duration_sec")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            raise ValueError("block duration must be a positive integer")
        total_duration += duration
        cadence = block.get("target_cadence")
        if cadence is not None and (
            isinstance(cadence, bool) or not isinstance(cadence, int) or cadence <= 0
        ):
            raise ValueError("target_cadence must be a positive integer")

        def positive_number(key: str) -> bool:
            value = block.get(key)
            if value is None:
                return False
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a number")
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f"{key} must be greater than zero")
            if key.endswith("watts") and value > 32767:
                raise ValueError(f"{key} exceeds the FTMS range")
            return True

        if block["type"] == "steady":
            has_pct = positive_number("target_pct_ftp")
            has_watts = positive_number("target_watts")
            if not (has_pct or has_watts):
                raise ValueError("steady block needs a power target")
        else:
            start_pct = positive_number("start_pct_ftp")
            start_watts = positive_number("start_watts")
            end_pct = positive_number("end_pct_ftp")
            end_watts = positive_number("end_watts")
            if not (start_pct or start_watts) or not (end_pct or end_watts):
                raise ValueError("ramp block needs start and end power")
    if total_duration > 24 * 60 * 60:
        raise ValueError("workout duration exceeds 24 hours")
    # Reject values that JSONB could store but the desktop format cannot round-trip.
    json.dumps(payload, allow_nan=False)
    return payload


def validate_source_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("source_name must be a string")
    name = PurePath(value.strip()).name
    if not name or name in {".", ".."}:
        raise ValueError("source_name is required")
    if not name.casefold().endswith(".json"):
        name += ".json"
    if len(name) > 255:
        raise ValueError("source_name is too long")
    return name
