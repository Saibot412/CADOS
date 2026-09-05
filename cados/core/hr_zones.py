"""Heart rate zones based on Garmin's 5-zone model (percentage of max HR)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HRZone:
    index: int
    name: str
    lower_pct: float
    upper_pct: float | None
    color: str

    @property
    def code(self) -> str:
        return f"Z{self.index}"

    @property
    def label(self) -> str:
        return f"{self.code} {self.name}"


HR_ZONES: tuple[HRZone, ...] = (
    HRZone(index=1, name="Locker", lower_pct=0.50, upper_pct=0.60, color="#8B98A7"),
    HRZone(index=2, name="Leicht", lower_pct=0.60, upper_pct=0.70, color="#2E86FF"),
    HRZone(index=3, name="Moderat", lower_pct=0.70, upper_pct=0.80, color="#2FBF71"),
    HRZone(index=4, name="Schwer", lower_pct=0.80, upper_pct=0.90, color="#FF9F43"),
    HRZone(index=5, name="Maximum", lower_pct=0.90, upper_pct=None, color="#EB5757"),
)


def hr_zone_for_bpm(heart_rate: int, max_hr: int) -> HRZone:
    """Return the HR zone for a given heart rate and max HR."""
    if max_hr <= 0 or heart_rate <= 0:
        return HR_ZONES[0]
    ratio = heart_rate / max_hr
    for zone in HR_ZONES:
        if zone.upper_pct is None or ratio < zone.upper_pct:
            return zone
    return HR_ZONES[-1]


def hr_zone_range_label(zone: HRZone, max_hr: int) -> str:
    """Return a human-readable BPM range label for a zone."""
    if max_hr <= 0:
        return "-"
    lower_bpm = round(zone.lower_pct * max_hr)
    if zone.upper_pct is None:
        return f"{lower_bpm}+ bpm"
    upper_bpm = round(zone.upper_pct * max_hr)
    return f"{lower_bpm}-{upper_bpm} bpm"


def hr_zone_pct_label(zone: HRZone) -> str:
    """Return percentage range label for a zone."""
    lower = round(zone.lower_pct * 100)
    if zone.upper_pct is None:
        return f"{lower}%+ HFmax"
    upper = round(zone.upper_pct * 100)
    return f"{lower}-{upper}% HFmax"
