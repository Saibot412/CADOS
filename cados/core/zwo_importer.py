from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from cados.core.workout_loader import WorkoutLoader, WorkoutValidationError
from cados.models.workout import WorkoutTemplate


class ZwoImportError(WorkoutValidationError):
    pass


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _number(element: ET.Element, key: str) -> float:
    try:
        value = float(element.attrib[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ZwoImportError(f"ZWO-Element {_tag(element)} benötigt {key}.") from exc
    if not math.isfinite(value) or value <= 0:
        raise ZwoImportError(f"ZWO-Wert {key} muss größer als 0 sein.")
    return value


def _duration(element: ET.Element, key: str = "Duration") -> int:
    value = _number(element, key)
    rounded = round(value)
    if abs(value - rounded) > 1e-6:
        raise ZwoImportError(f"ZWO-Wert {key} muss ganze Sekunden enthalten.")
    return rounded


def _power(element: ET.Element, key: str) -> float:
    value = _number(element, key)
    if value > 5:
        raise ZwoImportError(
            "ZWO-Workouts mit festen Wattwerten werden noch nicht unterstützt; "
            "erwartet werden FTP-Anteile wie 0.75."
        )
    return value


def _cadence(element: ET.Element, *keys: str) -> int | None:
    for key in keys:
        if key in element.attrib:
            return round(_number(element, key))
    return None


def parse_zwo(path: Path, loader: WorkoutLoader) -> WorkoutTemplate:
    with path.open("rb") as source:
        raw = source.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ZwoImportError("Die ZWO-Datei ist größer als 2 MB.")
    upper = raw.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ZwoImportError("ZWO-Dateien mit DTD oder Entities werden nicht unterstützt.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ZwoImportError(f"Ungültiges ZWO-XML: {exc}") from exc
    if _tag(root) != "workout_file":
        raise ZwoImportError("Die Datei enthält kein Zwift-workout_file.")

    def child_text(name: str, default: str = "") -> str:
        for child in root:
            if _tag(child) == name:
                return (child.text or "").strip()
        return default

    workout = next((child for child in root if _tag(child) == "workout"), None)
    if workout is None:
        raise ZwoImportError("Die ZWO-Datei enthält keinen workout-Abschnitt.")
    sport = child_text("sportType", "bike").casefold()
    if sport and sport not in {"bike", "cycling"}:
        raise ZwoImportError("CADOS kann nur Rad-Workouts aus ZWO importieren.")

    blocks: list[dict[str, Any]] = []
    for element in workout:
        kind = _tag(element)
        label = element.attrib.get("Name") or element.attrib.get("name") or kind
        if kind == "SteadyState":
            blocks.append({
                "type": "steady",
                "label": label,
                "duration_sec": _duration(element),
                "target_pct_ftp": _power(element, "Power"),
                "target_cadence": _cadence(element, "Cadence"),
            })
        elif kind in {"Warmup", "Ramp", "Cooldown"}:
            low = _power(element, "PowerLow")
            high = _power(element, "PowerHigh")
            start, end = (high, low) if kind == "Cooldown" else (low, high)
            blocks.append({
                "type": "ramp",
                "label": label,
                "duration_sec": _duration(element),
                "start_pct_ftp": start,
                "end_pct_ftp": end,
                "target_cadence": _cadence(element, "Cadence"),
            })
        elif kind == "IntervalsT":
            repeats = _duration(element, "Repeat")
            if repeats > 500:
                raise ZwoImportError("ZWO enthält mehr als 500 Wiederholungen.")
            for repeat in range(1, repeats + 1):
                blocks.extend((
                    {
                        "type": "steady",
                        "label": f"{label} {repeat} Belastung",
                        "duration_sec": _duration(element, "OnDuration"),
                        "target_pct_ftp": _power(element, "OnPower"),
                        "target_cadence": _cadence(element, "CadenceHigh", "Cadence"),
                    },
                    {
                        "type": "steady",
                        "label": f"{label} {repeat} Erholung",
                        "duration_sec": _duration(element, "OffDuration"),
                        "target_pct_ftp": _power(element, "OffPower"),
                        "target_cadence": _cadence(element, "CadenceResting", "CadenceLow", "Cadence"),
                    },
                ))
        elif kind in {"textevent", "TextEvent", "TextNotification"}:
            continue
        else:
            raise ZwoImportError(f"ZWO-Element {kind} wird von CADOS noch nicht unterstützt.")
        if len(blocks) > 2_000:
            raise ZwoImportError("Das ZWO-Workout enthält zu viele Blöcke.")

    payload = {
        "name": child_text("name", path.stem),
        "description": child_text("description"),
        "author": child_text("author", "Unbekannt"),
        "category": "Importiert / Zwift",
        "blocks": [{key: value for key, value in block.items() if value is not None} for block in blocks],
    }
    return loader.load_payload(payload, Path(f"imported/{path.stem}.json"))
