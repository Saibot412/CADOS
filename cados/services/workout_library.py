from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cados.models.workout import WorkoutTemplate


class WorkoutLibraryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RemoteWorkout:
    id: str
    source_name: str
    revision: int
    payload: dict


class WorkoutLibraryClient:
    MAX_RESPONSE_BYTES = 10_000_000

    def __init__(self, base_url: str, token: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.token)

    def _validate_url(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme == "https":
            return
        if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            return
        raise WorkoutLibraryError("Die Bibliothek benötigt HTTPS (außer bei localhost).")

    def _request(self, path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
        if not self.enabled:
            raise WorkoutLibraryError("Die zentrale Workout-Bibliothek ist nicht eingerichtet.")
        self._validate_url()
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Cados/0.2",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout, context=ssl.create_default_context()) as response:
                raw = response.read(self.MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise WorkoutLibraryError("Zugriff verweigert: Bibliotheks-Token prüfen.") from exc
            raise WorkoutLibraryError(f"Bibliotheksserver antwortet mit HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise WorkoutLibraryError(f"Bibliotheksserver nicht erreichbar: {exc}") from exc
        if len(raw) > self.MAX_RESPONSE_BYTES:
            raise WorkoutLibraryError("Antwort der Workout-Bibliothek ist zu groß.")
        try:
            result = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise WorkoutLibraryError("Bibliotheksserver lieferte ungültiges JSON.") from exc
        if not isinstance(result, dict):
            raise WorkoutLibraryError("Bibliotheksserver lieferte ein ungültiges Format.")
        return result

    def list_workouts(self) -> list[RemoteWorkout]:
        result = self._request("/api/v1/workouts")
        items = result.get("workouts")
        if not isinstance(items, list):
            raise WorkoutLibraryError("In der Serverantwort fehlt die Workout-Liste.")
        workouts: list[RemoteWorkout] = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                raise WorkoutLibraryError("Ein Server-Workout hat ein ungültiges Format.")
            workouts.append(RemoteWorkout(
                id=str(item.get("id") or ""),
                source_name=str(item.get("source_name") or "workout.json"),
                revision=max(1, int(item.get("revision") or 1)),
                payload=item["payload"],
            ))
        return workouts

    def publish(self, workout: WorkoutTemplate) -> RemoteWorkout:
        result = self._request("/api/v1/workouts", method="POST", payload={
            "source_name": workout.source_path.name,
            "payload": workout.to_dict(),
        })
        return RemoteWorkout(
            id=str(result["id"]),
            source_name=str(result["source_name"]),
            revision=int(result["revision"]),
            payload=dict(result["payload"]),
        )
