from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BlockKind = Literal["steady", "ramp"]
DEFAULT_FTP_WATTS = 200


def _pct_to_label(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{round(value * 100)}% FTP"


def _resolve_target_watts(pct_ftp: float | None, watts: int | None, ftp_watts: int) -> int | None:
    if pct_ftp is not None:
        return max(1, round(ftp_watts * pct_ftp))
    if watts is not None:
        return watts
    return None


@dataclass(slots=True)
class WorkoutTemplateBlock:
    kind: BlockKind
    label: str
    duration_sec: int
    target_cadence: int | None = None
    target_pct_ftp: float | None = None
    target_watts: int | None = None
    start_pct_ftp: float | None = None
    end_pct_ftp: float | None = None
    start_watts: int | None = None
    end_watts: int | None = None

    @property
    def average_watts(self) -> int:
        if self.kind == "steady":
            return int(self.target_watts or 0)
        return round(((self.start_watts or 0) + (self.end_watts or 0)) / 2)

    @property
    def watts_summary(self) -> str:
        if self.kind == "steady":
            if self.target_pct_ftp is not None:
                return _pct_to_label(self.target_pct_ftp) or "-"
            return f"{self.target_watts} W"
        if self.start_pct_ftp is not None or self.end_pct_ftp is not None:
            start_label = _pct_to_label(self.start_pct_ftp) or "-"
            end_label = _pct_to_label(self.end_pct_ftp) or "-"
            return f"{start_label} -> {end_label}"
        return f"{self.start_watts}->{self.end_watts} W"

    def resolve(self, ftp_watts: int) -> "ResolvedWorkoutBlock":
        if self.kind == "steady":
            resolved_target = _resolve_target_watts(self.target_pct_ftp, self.target_watts, ftp_watts)
            if resolved_target is None:
                raise ValueError(f"Steady block '{self.label}' cannot be resolved.")
            return ResolvedWorkoutBlock(
                kind="steady",
                label=self.label,
                duration_sec=self.duration_sec,
                target_cadence=self.target_cadence,
                target_watts=resolved_target,
                target_pct_ftp=self.target_pct_ftp,
            )

        resolved_start = _resolve_target_watts(self.start_pct_ftp, self.start_watts, ftp_watts)
        resolved_end = _resolve_target_watts(self.end_pct_ftp, self.end_watts, ftp_watts)
        if resolved_start is None or resolved_end is None:
            raise ValueError(f"Ramp block '{self.label}' cannot be resolved.")
        return ResolvedWorkoutBlock(
            kind="ramp",
            label=self.label,
            duration_sec=self.duration_sec,
            target_cadence=self.target_cadence,
            start_watts=resolved_start,
            end_watts=resolved_end,
            start_pct_ftp=self.start_pct_ftp,
            end_pct_ftp=self.end_pct_ftp,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.kind,
            "label": self.label,
            "duration_sec": self.duration_sec,
        }
        if self.target_cadence is not None:
            payload["target_cadence"] = self.target_cadence
        if self.kind == "steady":
            if self.target_pct_ftp is not None:
                payload["target_pct_ftp"] = self.target_pct_ftp
            if self.target_watts is not None:
                payload["target_watts"] = self.target_watts
        else:
            if self.start_pct_ftp is not None:
                payload["start_pct_ftp"] = self.start_pct_ftp
            if self.end_pct_ftp is not None:
                payload["end_pct_ftp"] = self.end_pct_ftp
            if self.start_watts is not None:
                payload["start_watts"] = self.start_watts
            if self.end_watts is not None:
                payload["end_watts"] = self.end_watts
        return payload


@dataclass(slots=True)
class ResolvedWorkoutBlock:
    kind: BlockKind
    label: str
    duration_sec: int
    target_cadence: int | None = None
    target_watts: int | None = None
    start_watts: int | None = None
    end_watts: int | None = None
    target_pct_ftp: float | None = None
    start_pct_ftp: float | None = None
    end_pct_ftp: float | None = None

    def target_watts_at(self, seconds_into_block: float) -> int:
        if self.kind == "steady":
            return int(self.target_watts or 0)

        start = int(self.start_watts or 0)
        end = int(self.end_watts or start)
        if self.duration_sec <= 0:
            return end

        progress = min(max(seconds_into_block / self.duration_sec, 0.0), 1.0)
        return round(start + progress * (end - start))

    def target_pct_ftp_at(self, seconds_into_block: float, ftp_watts: int) -> float | None:
        if self.kind == "steady":
            if self.target_pct_ftp is not None:
                return self.target_pct_ftp
            return (self.target_watts or 0) / ftp_watts if ftp_watts > 0 and self.target_watts is not None else None

        if self.start_pct_ftp is not None and self.end_pct_ftp is not None and self.duration_sec > 0:
            progress = min(max(seconds_into_block / self.duration_sec, 0.0), 1.0)
            return self.start_pct_ftp + progress * (self.end_pct_ftp - self.start_pct_ftp)

        current_watts = self.target_watts_at(seconds_into_block)
        return current_watts / ftp_watts if ftp_watts > 0 else None

    @property
    def average_watts(self) -> int:
        if self.kind == "steady":
            return int(self.target_watts or 0)
        return round(((self.start_watts or 0) + (self.end_watts or 0)) / 2)

    @property
    def watts_summary(self) -> str:
        if self.kind == "steady":
            return f"{self.target_watts} W"
        return f"{self.start_watts}->{self.end_watts} W"

    @property
    def pct_summary(self) -> str | None:
        if self.kind == "steady":
            return _pct_to_label(self.target_pct_ftp)
        if self.start_pct_ftp is None and self.end_pct_ftp is None:
            return None
        start_label = _pct_to_label(self.start_pct_ftp) or "-"
        end_label = _pct_to_label(self.end_pct_ftp) or "-"
        return f"{start_label} -> {end_label}"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.kind,
            "label": self.label,
            "duration_sec": self.duration_sec,
        }
        if self.target_cadence is not None:
            payload["target_cadence"] = self.target_cadence
        if self.kind == "steady":
            payload["target_watts"] = self.target_watts
            if self.target_pct_ftp is not None:
                payload["target_pct_ftp"] = self.target_pct_ftp
        else:
            payload["start_watts"] = self.start_watts
            payload["end_watts"] = self.end_watts
            if self.start_pct_ftp is not None:
                payload["start_pct_ftp"] = self.start_pct_ftp
            if self.end_pct_ftp is not None:
                payload["end_pct_ftp"] = self.end_pct_ftp
        return payload


@dataclass(slots=True)
class WorkoutTemplate:
    name: str
    description: str
    author: str
    ftp_reference: int | None
    blocks: tuple[WorkoutTemplateBlock, ...]
    source_path: Path
    category: str = ""
    sort_order: int = 0
    best_for: str = ""
    when_to_do: str = ""
    skip_if: str = ""

    @property
    def total_duration_sec(self) -> int:
        return sum(block.duration_sec for block in self.blocks)

    @property
    def total_blocks(self) -> int:
        return len(self.blocks)

    def resolve(self, ftp_watts: int | None = None, default_ftp_watts: int = DEFAULT_FTP_WATTS) -> "ResolvedWorkout":
        effective_ftp = int(ftp_watts or self.ftp_reference or default_ftp_watts)
        if effective_ftp <= 0:
            effective_ftp = default_ftp_watts

        return ResolvedWorkout(
            name=self.name,
            description=self.description,
            category=self.category,
            sort_order=self.sort_order,
            best_for=self.best_for,
            when_to_do=self.when_to_do,
            skip_if=self.skip_if,
            author=self.author,
            ftp_reference=self.ftp_reference,
            ftp_watts=effective_ftp,
            blocks=tuple(block.resolve(effective_ftp) for block in self.blocks),
            source_path=self.source_path,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "sort_order": self.sort_order,
            "best_for": self.best_for,
            "when_to_do": self.when_to_do,
            "skip_if": self.skip_if,
            "author": self.author,
            "ftp_reference": self.ftp_reference,
            "blocks": [block.to_dict() for block in self.blocks],
        }


@dataclass(slots=True)
class ResolvedWorkout:
    name: str
    description: str
    author: str
    ftp_reference: int | None
    ftp_watts: int
    blocks: tuple[ResolvedWorkoutBlock, ...]
    source_path: Path
    category: str = ""
    sort_order: int = 0
    best_for: str = ""
    when_to_do: str = ""
    skip_if: str = ""

    @property
    def total_duration_sec(self) -> int:
        return sum(block.duration_sec for block in self.blocks)

    @property
    def total_blocks(self) -> int:
        return len(self.blocks)

    def locate_block(self, elapsed_sec: float) -> tuple[int, ResolvedWorkoutBlock, float]:
        if not self.blocks:
            raise ValueError("Workout contains no blocks.")

        if self.total_duration_sec <= 0:
            return 0, self.blocks[0], 0.0

        clamped = min(max(elapsed_sec, 0.0), max(self.total_duration_sec - 1e-6, 0.0))
        cursor = 0.0
        for index, block in enumerate(self.blocks):
            block_end = cursor + block.duration_sec
            if clamped < block_end or index == len(self.blocks) - 1:
                return index, block, clamped - cursor
            cursor = block_end

        return len(self.blocks) - 1, self.blocks[-1], float(self.blocks[-1].duration_sec)

    def block_start_offset(self, block_index: int) -> int:
        return sum(block.duration_sec for block in self.blocks[:block_index])

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "sort_order": self.sort_order,
            "best_for": self.best_for,
            "when_to_do": self.when_to_do,
            "skip_if": self.skip_if,
            "author": self.author,
            "ftp_reference": self.ftp_reference,
            "ftp_watts": self.ftp_watts,
            "blocks": [block.to_dict() for block in self.blocks],
        }
