from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from cados.models.workout import ResolvedWorkout, ResolvedWorkoutBlock


@dataclass(frozen=True, slots=True)
class PowerZone:
    index: int
    name: str
    lower_ratio: float
    upper_ratio: float | None
    color: str

    @property
    def code(self) -> str:
        return f"Z{self.index}"

    @property
    def label(self) -> str:
        return f"{self.code} {self.name}"


@dataclass(frozen=True, slots=True)
class ZoneSummaryEntry:
    zone: PowerZone
    duration_sec: int
    percentage: float
    watt_range_label: str
    pct_range_label: str


@dataclass(frozen=True, slots=True)
class BlockZoneSegment:
    zone: PowerZone
    start_progress: float
    end_progress: float
    start_watts: float
    end_watts: float


POWER_ZONES: tuple[PowerZone, ...] = (
    PowerZone(index=1, name="Recovery", lower_ratio=0.0, upper_ratio=0.55, color="#8B98A7"),
    PowerZone(index=2, name="Endurance", lower_ratio=0.56, upper_ratio=0.75, color="#2E86FF"),
    PowerZone(index=3, name="Tempo", lower_ratio=0.76, upper_ratio=0.90, color="#2FBF71"),
    PowerZone(index=4, name="Threshold", lower_ratio=0.91, upper_ratio=1.05, color="#F2C94C"),
    PowerZone(index=5, name="VO2 Max", lower_ratio=1.06, upper_ratio=1.20, color="#FF9F43"),
    PowerZone(index=6, name="Anaerobic", lower_ratio=1.21, upper_ratio=1.50, color="#EB5757"),
    PowerZone(index=7, name="Neuromuscular", lower_ratio=1.51, upper_ratio=None, color="#9B51E0"),
)


def round_half_up(value: float) -> int:
    return int(floor(value + 0.5))


def power_zone_for_watts(watts: float, ftp_watts: int) -> PowerZone:
    effective_ftp = max(1, int(ftp_watts or 0))
    ratio = max(0.0, watts) / effective_ftp
    for zone in POWER_ZONES:
        if zone.upper_ratio is None or ratio <= zone.upper_ratio:
            return zone
    return POWER_ZONES[-1]


def power_zone_bounds_watts(zone: PowerZone, ftp_watts: int) -> tuple[int, int | None]:
    effective_ftp = max(1, int(ftp_watts or 0))
    previous_upper = 0
    for current in POWER_ZONES:
        upper = None if current.upper_ratio is None else round_half_up(effective_ftp * current.upper_ratio)
        lower = 0 if current.index == 1 else previous_upper + 1
        if current.index == zone.index:
            return lower, upper
        if upper is not None:
            previous_upper = upper
    return 0, None


def zone_watt_range_label(zone: PowerZone, ftp_watts: int) -> str:
    lower, upper = power_zone_bounds_watts(zone, ftp_watts)
    if upper is None:
        return f"{lower}+ W"
    return f"{lower}-{upper} W"


def zone_pct_range_label(zone: PowerZone) -> str:
    lower = round_half_up(zone.lower_ratio * 100)
    if zone.index == 1:
        lower = 0
    if zone.upper_ratio is None:
        return f"{lower}%+ FTP"
    upper = round_half_up(zone.upper_ratio * 100)
    return f"{lower}-{upper}% FTP"


def build_zone_summary(
    zone_durations_sec: Sequence[float],
    ftp_watts: int,
    total_duration_sec: float | None = None,
) -> tuple[ZoneSummaryEntry, ...]:
    total = total_duration_sec if total_duration_sec is not None else sum(zone_durations_sec)
    summary: list[ZoneSummaryEntry] = []
    for index, zone in enumerate(POWER_ZONES):
        seconds = zone_durations_sec[index] if index < len(zone_durations_sec) else 0.0
        percentage = 0.0 if total <= 0 else (seconds / total) * 100.0
        summary.append(
            ZoneSummaryEntry(
                zone=zone,
                duration_sec=round_half_up(seconds),
                percentage=percentage,
                watt_range_label=zone_watt_range_label(zone, ftp_watts),
                pct_range_label=zone_pct_range_label(zone),
            )
        )
    return tuple(summary)


def summarize_workout_zones(workout: ResolvedWorkout | None) -> tuple[ZoneSummaryEntry, ...]:
    if workout is None:
        return ()

    zone_durations = [0.0] * len(POWER_ZONES)
    for block in workout.blocks:
        _add_block_zone_durations(block, workout.ftp_watts, zone_durations)
    return build_zone_summary(zone_durations, workout.ftp_watts, workout.total_duration_sec)


def split_block_into_zone_segments(block: ResolvedWorkoutBlock, ftp_watts: int) -> tuple[BlockZoneSegment, ...]:
    if block.duration_sec <= 0:
        return ()

    if block.kind == "steady":
        watts = float(block.target_watts or 0)
        zone = power_zone_for_watts(watts, ftp_watts)
        return (
            BlockZoneSegment(
                zone=zone,
                start_progress=0.0,
                end_progress=1.0,
                start_watts=watts,
                end_watts=watts,
            ),
        )

    start_watts = float(block.start_watts or 0)
    end_watts = float(block.end_watts or start_watts)
    if abs(end_watts - start_watts) < 1e-9:
        zone = power_zone_for_watts(start_watts, ftp_watts)
        return (
            BlockZoneSegment(
                zone=zone,
                start_progress=0.0,
                end_progress=1.0,
                start_watts=start_watts,
                end_watts=end_watts,
            ),
        )

    min_watts = min(start_watts, end_watts)
    max_watts = max(start_watts, end_watts)
    cut_points = [0.0, 1.0]

    for zone in POWER_ZONES[:-1]:
        assert zone.upper_ratio is not None
        boundary_watts = ftp_watts * zone.upper_ratio
        if min_watts < boundary_watts < max_watts:
            cut_points.append((boundary_watts - start_watts) / (end_watts - start_watts))

    ordered = sorted({min(1.0, max(0.0, point)) for point in cut_points})
    segments: list[BlockZoneSegment] = []
    for start_progress, end_progress in zip(ordered, ordered[1:]):
        if end_progress <= start_progress:
            continue

        segment_start_watts = start_watts + (end_watts - start_watts) * start_progress
        segment_end_watts = start_watts + (end_watts - start_watts) * end_progress
        midpoint = (start_progress + end_progress) * 0.5
        midpoint_watts = start_watts + (end_watts - start_watts) * midpoint
        segments.append(
            BlockZoneSegment(
                zone=power_zone_for_watts(midpoint_watts, ftp_watts),
                start_progress=start_progress,
                end_progress=end_progress,
                start_watts=segment_start_watts,
                end_watts=segment_end_watts,
            )
        )
    return tuple(segments)


def _add_block_zone_durations(block: ResolvedWorkoutBlock, ftp_watts: int, zone_durations: list[float]) -> None:
    for segment in split_block_into_zone_segments(block, ftp_watts):
        zone_durations[segment.zone.index - 1] += block.duration_sec * (segment.end_progress - segment.start_progress)
