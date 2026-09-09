"""Derive profile suggestions from recorded measurements, never target power."""
from __future__ import annotations

import math
from cados.core.training_metrics import TrainingMetrics


def is_ftp_ramp(name: str) -> bool:
    name = str(name).casefold()
    return "ftp" in name and "ramp" in name


def measured_max_hr(samples: list[dict]) -> int | None:
    values = [s.get("heart_rate") for s in samples if isinstance(s, dict)]
    valid = [int(v) for v in values if type(v) in (int, float) and math.isfinite(v) and 50 <= v <= 250 and v == int(v)]
    return max(valid, default=None)


def ftp_test_result(payload: dict) -> dict | None:
    if not is_ftp_ramp(payload.get("workout_name", "")):
        return None
    blocks = (payload.get("workout_payload") or {}).get("blocks", [])
    start, end, cursor = None, None, 0
    for block in blocks:
        duration = block.get("duration_sec", 0)
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            return None
        if str(block.get("label", "")).casefold().startswith(("step ", "stufe ")):
            start = cursor if start is None else start
            end = cursor + duration
        cursor += duration
    result = {"old_ftp": payload.get("ftp_watts"), "method": "75_percent_best_continuous_minute", "eligible": False}
    if start is None:
        return {**result, "reason": "Für diesen Test ist kein auswertbarer Stufenteil hinterlegt."}
    metrics = TrainingMetrics()
    previous_end, segment, counted = None, None, 0.0
    for sample in payload.get("samples") or []:
        if not isinstance(sample, dict):
            continue
        dt, elapsed, watts = sample.get("duration_sec"), sample.get("workout_elapsed_sec"), sample.get("watts")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (dt, elapsed, watts)):
            continue
        if dt <= 0 or dt > 86400 or not 0 <= watts <= 32767:
            continue
        lower, upper = max(start, elapsed), min(end, elapsed + dt)
        if upper <= lower:
            continue
        if segment != sample.get("segment", 0) or (previous_end is not None and abs(lower - previous_end) > .01):
            metrics.break_power_window()
        segment, previous_end = sample.get("segment", 0), upper
        length = min(upper - lower, 86400 - counted)
        if length <= 0:
            break
        counted += length
        metrics.add(length, watts, 0, None, lower, 0)
    best = round(metrics.best_minute)
    estimate = round(metrics.best_minute * .75)
    if not 30 <= estimate <= 2000:
        return {**result, "reason": "Im Belastungsteil fehlt eine vollständige, zusammenhängende Minute mit verwertbarer Leistung."}
    return {**result, "eligible": True, "best_minute_watts": best, "estimated_ftp": estimate}
