from __future__ import annotations

from collections import deque
from typing import Any


class TrainingMetrics:
    """Time-weighted measurements, with one-second bins for rolling power."""

    def __init__(self) -> None:
        self.active_seconds = 0.0
        self.energy = 0.0
        self.cadence_sum = 0.0
        self.hr_sum = 0.0
        self.hr_seconds = 0.0
        self.samples: list[dict[str, Any]] = []
        self._bin_time = 0.0
        self._bin_energy = 0.0
        self._seconds: deque[float] = deque(maxlen=60)
        self._np_sum = 0.0
        self._np_count = 0
        self.best_minute = 0.0
        self.max_heart_rate = 0
        self._segment = 0

    def break_power_window(self) -> None:
        self._seconds.clear()
        self._bin_time = self._bin_energy = 0.0
        self._segment += 1

    def add(self, dt: float, watts: int, cadence: int, heart_rate: int | None,
            workout_elapsed_sec: float, target_watts: int) -> None:
        if dt <= 0:
            return
        watts = max(0, watts)
        self.energy += watts * dt
        self.cadence_sum += cadence * dt
        if heart_rate is not None and heart_rate > 0:
            self.hr_sum += heart_rate * dt
            self.hr_seconds += dt
            if 50 <= heart_rate <= 250:
                self.max_heart_rate = max(self.max_heart_rate, heart_rate)
        self.active_seconds += dt
        self.samples.append({
            "segment": self._segment,
            "elapsed_sec": round(self.active_seconds, 6),
            "duration_sec": dt,
            "workout_elapsed_sec": workout_elapsed_sec,
            "watts": watts,
            "cadence": cadence,
            "heart_rate": heart_rate,
            "target_watts": target_watts,
        })
        remaining = dt
        while remaining > 1e-9:
            portion = min(remaining, 1.0 - self._bin_time)
            self._bin_time += portion
            self._bin_energy += watts * portion
            remaining -= portion
            if self._bin_time >= 1.0 - 1e-9:
                self._seconds.append(self._bin_energy / self._bin_time)
                self._bin_time = self._bin_energy = 0.0
                if len(self._seconds) >= 30:
                    self._np_sum += (sum(list(self._seconds)[-30:]) / 30) ** 4
                    self._np_count += 1
                if len(self._seconds) == 60:
                    self.best_minute = max(self.best_minute, sum(self._seconds) / 60)

    def summary(self, ftp: int) -> dict[str, int | float]:
        avg = round(self.energy / self.active_seconds) if self.active_seconds else 0
        np = round((self._np_sum / self._np_count) ** 0.25) if self._np_count else avg
        intensity = np / ftp if ftp > 0 else 0.0
        return {
            "max_heart_rate": self.max_heart_rate,
            "avg_watts": avg,
            "avg_cadence": round(self.cadence_sum / self.active_seconds) if self.active_seconds else 0,
            "avg_heart_rate": round(self.hr_sum / self.hr_seconds) if self.hr_seconds else 0,
            "normalized_power": np,
            "intensity_factor": round(intensity, 2),
            "tss": round(self.active_seconds / 3600 * intensity ** 2 * 100, 1),
            "calories": round(self.energy / 1000),
        }
