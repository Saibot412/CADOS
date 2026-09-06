"""Workout parsing is usable without desktop or Bluetooth dependencies."""
from cados.core.workout_loader import WorkoutLoader, WorkoutValidationError

__all__ = ["TrainingSnapshot", "WorkoutEngine", "WorkoutLoader", "WorkoutValidationError"]


def __getattr__(name: str):
    # Preserve the public desktop imports without loading hardware services when
    # the server imports a parser submodule.
    if name in {"TrainingSnapshot", "WorkoutEngine"}:
        from cados.core.workout_engine import TrainingSnapshot, WorkoutEngine

        globals().update(TrainingSnapshot=TrainingSnapshot, WorkoutEngine=WorkoutEngine)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
