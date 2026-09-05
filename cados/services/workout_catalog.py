from __future__ import annotations

from pathlib import Path

from cados.core.workout_loader import WorkoutLoader, WorkoutValidationError
from cados.core.zwo_importer import parse_zwo
from cados.models.workout import WorkoutTemplate
from cados.services.storage import DataStore
from cados.services.workout_library import RemoteWorkout, WorkoutLibraryClient


class WorkoutCatalog:
    def __init__(self, bundled_dir: Path, store: DataStore):
        self.bundled_dir = bundled_dir
        self.store = store
        self.loader = WorkoutLoader(bundled_dir)

    def scan(self) -> list[WorkoutTemplate]:
        by_name = {workout.source_path.name.casefold(): workout for workout in self.loader.scan()}
        for item in self.store.list_workouts():
            try:
                workout = self.loader.load_payload(
                    item["payload"], Path("library") / item["source_name"]
                )
            except WorkoutValidationError:
                continue
            by_name[workout.source_path.name.casefold()] = workout
        return list(by_name.values())

    def import_file(self, path: Path) -> WorkoutTemplate:
        suffix = path.suffix.casefold()
        if suffix == ".json":
            workout = self.loader.load_path(path)
        elif suffix == ".zwo":
            workout = parse_zwo(path, self.loader)
        else:
            raise WorkoutValidationError("Unterstützt werden CADOS-JSON und Zwift-ZWO.")
        source_name = f"{path.stem}.json"
        self.store.save_workout(workout.to_dict(), source_name, origin="import")
        return self.loader.load_payload(workout.to_dict(), Path("library") / source_name)

    def load_path(self, path: Path) -> WorkoutTemplate:
        return self.loader.load_path(path)

    def load_payload(self, payload: dict, source_path: Path) -> WorkoutTemplate:
        return self.loader.load_payload(payload, source_path)

    def save_remote(self, item: RemoteWorkout) -> WorkoutTemplate:
        workout = self.loader.load_payload(
            item.payload, Path("library") / item.source_name
        )
        self.store.save_workout(
            workout.to_dict(),
            item.source_name,
            origin="server",
            workout_id=item.id,
            revision=item.revision,
        )
        return workout

    def sync(self, client: WorkoutLibraryClient) -> int:
        imported = 0
        for item in client.list_workouts():
            self.save_remote(item)
            imported += 1
        return imported

    def get_by_source_name(self, source_name: str) -> WorkoutTemplate | None:
        return next(
            (workout for workout in self.scan() if workout.source_path.name == source_name),
            None,
        )
