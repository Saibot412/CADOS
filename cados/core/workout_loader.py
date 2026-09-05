from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from cados.models.workout import WorkoutTemplate, WorkoutTemplateBlock

logger = logging.getLogger(__name__)


class WorkoutValidationError(ValueError):
    pass


class WorkoutLoader:
    def __init__(self, workouts_dir: Path):
        self.workouts_dir = workouts_dir

    def scan(self) -> list[WorkoutTemplate]:
        workouts: list[WorkoutTemplate] = []
        for path in sorted(self.workouts_dir.glob("*.json")):
            try:
                workouts.append(self.load_path(path))
            except (OSError, UnicodeError, json.JSONDecodeError, WorkoutValidationError) as exc:
                logger.warning("Workout '%s' konnte nicht geladen werden: %s", path.name, exc)
        return workouts

    def load_path(self, path: Path) -> WorkoutTemplate:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise WorkoutValidationError("Workout root must be an object.")
        return self.load_payload(payload, source_path=path)

    def load_payload(self, payload: dict[str, Any], source_path: Path) -> WorkoutTemplate:
        try:
            return self._load_payload(payload, source_path)
        except (TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, WorkoutValidationError):
                raise
            raise WorkoutValidationError(f"Invalid workout value: {exc}") from exc

    def _load_payload(self, payload: dict[str, Any], source_path: Path) -> WorkoutTemplate:
        if not isinstance(payload, dict):
            raise WorkoutValidationError("Workout root must be an object.")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise WorkoutValidationError("Workout requires a name.")

        raw_blocks = payload.get("blocks")
        if not isinstance(raw_blocks, list) or not raw_blocks:
            raise WorkoutValidationError("Workout requires at least one block.")

        blocks: list[WorkoutTemplateBlock] = []
        for index, raw_block in enumerate(raw_blocks, start=1):
            if not isinstance(raw_block, dict):
                raise WorkoutValidationError(f"Block {index} must be an object.")
            blocks.append(self._parse_block(raw_block, index))

        return WorkoutTemplate(
            name=name,
            description=str(payload.get("description") or ""),
            author=str(payload.get("author") or "Unbekannt"),
            ftp_reference=self._optional_positive_int(payload, "ftp_reference"),
            blocks=tuple(blocks),
            source_path=source_path,
            category=str(payload.get("category") or ""),
            sort_order=self._integer(payload.get("sort_order") or 0, "sort_order"),
            best_for=str(payload.get("best_for") or ""),
            when_to_do=str(payload.get("when_to_do") or ""),
            skip_if=str(payload.get("skip_if") or ""),
        )

    def _parse_block(self, raw_block: dict[str, Any], index: int) -> WorkoutTemplateBlock:
        kind = str(raw_block.get("type") or "").strip().lower()
        if kind not in {"steady", "ramp"}:
            raise WorkoutValidationError(f"Unsupported block type in block {index}: {kind!r}")

        duration_sec = self._integer(raw_block.get("duration_sec") or 0, "duration_sec")
        if duration_sec <= 0:
            raise WorkoutValidationError(f"Block {index} requires duration_sec > 0.")

        label = str(raw_block.get("label") or f"Block {index}")
        cadence = self._optional_positive_int(raw_block, "target_cadence")

        if kind == "steady":
            target_pct_ftp = self._optional_pct(raw_block, "target_pct_ftp")
            target_watts = self._optional_positive_int(raw_block, "target_watts")
            if target_pct_ftp is None and target_watts is None:
                raise WorkoutValidationError(
                    f"Steady block {index} requires target_pct_ftp or target_watts."
                )
            return WorkoutTemplateBlock(
                kind="steady",
                label=label,
                duration_sec=duration_sec,
                target_cadence=cadence,
                target_pct_ftp=target_pct_ftp,
                target_watts=target_watts,
            )

        start_pct_ftp = self._optional_pct(raw_block, "start_pct_ftp")
        end_pct_ftp = self._optional_pct(raw_block, "end_pct_ftp")
        start_watts = self._optional_positive_int(raw_block, "start_watts")
        end_watts = self._optional_positive_int(raw_block, "end_watts")
        if start_pct_ftp is None and start_watts is None:
            raise WorkoutValidationError(
                f"Ramp block {index} requires start_pct_ftp or start_watts."
            )
        if end_pct_ftp is None and end_watts is None:
            raise WorkoutValidationError(
                f"Ramp block {index} requires end_pct_ftp or end_watts."
            )
        return WorkoutTemplateBlock(
            kind="ramp",
            label=label,
            duration_sec=duration_sec,
            target_cadence=cadence,
            start_pct_ftp=start_pct_ftp,
            end_pct_ftp=end_pct_ftp,
            start_watts=start_watts,
            end_watts=end_watts,
        )

    @staticmethod
    def _integer(value: Any, key: str) -> int:
        if isinstance(value, bool):
            raise WorkoutValidationError(f"Field '{key}' must be an integer.")
        parsed = int(value)
        if float(value) != parsed:
            raise WorkoutValidationError(f"Field '{key}' must be an integer.")
        return parsed

    @staticmethod
    def _optional_positive_int(raw_block: dict[str, Any], key: str) -> int | None:
        value = raw_block.get(key)
        if value is None:
            return None
        parsed = WorkoutLoader._integer(value, key)
        if parsed <= 0:
            raise WorkoutValidationError(f"Field '{key}' must be > 0.")
        if key.endswith("watts") and parsed > 32767:
            raise WorkoutValidationError(f"Field '{key}' exceeds the FTMS power range.")
        return parsed

    @staticmethod
    def _optional_pct(raw_block: dict[str, Any], key: str) -> float | None:
        value = raw_block.get(key)
        if value is None:
            return None
        if isinstance(value, bool):
            raise WorkoutValidationError(f"Field '{key}' must be a number.")
        parsed = float(value)
        if not math.isfinite(parsed) or parsed <= 0:
            raise WorkoutValidationError(f"Field '{key}' must be > 0.")
        return parsed
