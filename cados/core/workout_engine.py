from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from cados.core.zones import power_zone_for_watts
from cados.core.training_metrics import TrainingMetrics
from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord
from cados.models.workout import DEFAULT_FTP_WATTS, ResolvedWorkout, WorkoutTemplate
from cados.services.hr_monitor import HRMonitorService
from cados.services.trainer import TrainerController


@dataclass(slots=True)
class TrainingSnapshot:
    state: str
    workout_name: str
    elapsed_sec: int
    remaining_sec: int
    current_block_name: str
    block_index: int
    block_count: int
    current_watts: int
    current_cadence: int
    target_watts: int
    target_cadence: int | None
    target_pct_label: str | None
    adjustment_watts: int
    zone_label: str
    trainer_label: str
    trainer_connected: bool
    active_sec: int = 0
    heart_rate: int = 0
    hr_connected: bool = False
    auto_paused: bool = False
    ramping: bool = False
    avg_watts: int = 0
    avg_cadence: int = 0
    max_heart_rate: int = 0
    avg_heart_rate: int = 0
    normalized_power: int = 0
    intensity_factor: float = 0.0
    tss: float = 0.0
    calories: int = 0
    trainer_target_watts: int = 0
    adaptive_erg: bool = False
    adaptive_relief_watts: int = 0


class WorkoutEngine:
    RAMP_DURATION_SEC = 5.0
    RAMP_START_WATTS = 30
    ZERO_WATTS_PAUSE_DELAY_SEC = 2.0
    BLOCK_TRANSITION_SEC = 3.0
    MAX_TICK_GAP_SEC = 5.0
    ADAPTIVE_ERG_DEADBAND_RPM = 3
    ADAPTIVE_ERG_TRIGGER_SEC = 2.0
    ADAPTIVE_ERG_MAX_RELIEF_RATIO = 0.10
    ADAPTIVE_ERG_RELIEF_RATE_WATTS_PER_SEC = 5.0
    ADAPTIVE_ERG_RECOVERY_RATE_WATTS_PER_SEC = 4.0

    def __init__(self, trainer: TrainerController, hr_monitor: HRMonitorService | None = None):
        self.trainer = trainer
        self.hr_monitor = hr_monitor
        self.workout_template: WorkoutTemplate | None = None
        self.workout: ResolvedWorkout | None = None
        self.profile: UserProfile | None = None
        self.state = "idle"
        self.elapsed_sec = 0.0
        self.adjustment_watts = 0
        self.started_at: str | None = None
        self._pending_session: WorkoutSessionRecord | None = None
        self._zero_watts_sec = 0.0
        self._ramp_elapsed_sec = 0.0
        self._ramping = False
        self._auto_paused = False
        self._last_block_index: int = -1
        self._last_target_watts: int = 0
        self._block_transition_from_watts: int | None = None
        self._block_transition_elapsed: float = 0.0
        self.adaptive_erg = False
        self._adaptive_low_cadence_sec = 0.0
        self._adaptive_relief_watts = 0.0
        self._reset_metrics()

    def _reset_metrics(self) -> None:
        self.metrics = TrainingMetrics()

    def set_profile(self, profile: UserProfile | None) -> None:
        self.profile = profile

    def set_adaptive_erg(self, enabled: bool) -> TrainingSnapshot:
        """Switch ERG controllers safely, including while a workout is running."""
        self.adaptive_erg = bool(enabled) and not self.is_ftp_test
        self._adaptive_low_cadence_sec = 0.0
        self._adaptive_relief_watts = 0.0
        if self.workout is None:
            return self.snapshot()
        return self._apply_control()

    def load_workout(self, workout_template: WorkoutTemplate, ftp_watts: int | None = None) -> TrainingSnapshot:
        if self.state in {"running", "paused", "waiting_for_pedal"}:
            raise ValueError("Stop the current workout before loading another.")
        if self._pending_session is not None:
            raise ValueError("Save the previous session before loading another workout.")
        resolved_ftp = ftp_watts or (self.profile.ftp_watts if self.profile else None)
        self.workout_template = workout_template
        self.workout = workout_template.resolve(resolved_ftp, default_ftp_watts=DEFAULT_FTP_WATTS)
        if self.is_ftp_test:
            self.adaptive_erg = False
        self.state = "ready"
        self.elapsed_sec = 0.0
        self.adjustment_watts = 0
        self._pending_session = None
        self._zero_watts_sec = 0.0
        self._ramp_elapsed_sec = 0.0
        self._ramping = False
        self._auto_paused = False
        self._last_block_index = -1
        self._last_target_watts = 0
        self._block_transition_from_watts = None
        self._block_transition_elapsed = 0.0
        self._adaptive_low_cadence_sec = 0.0
        self._adaptive_relief_watts = 0.0
        self._reset_metrics()
        return self.snapshot()

    def start(self) -> TrainingSnapshot:
        if self.workout is None:
            raise ValueError("No workout loaded.")
        if self.state not in {"ready", "stopped", "completed"}:
            return self.snapshot()
        if self._pending_session is not None:
            raise ValueError("Save the previous session before restarting.")
        self.state = "waiting_for_pedal"
        self.elapsed_sec = 0.0
        self.adjustment_watts = 0
        self.started_at = datetime.now(tz=UTC).isoformat()
        self._pending_session = None
        self._zero_watts_sec = 0.0
        self._ramp_elapsed_sec = 0.0
        self._ramping = False
        self._auto_paused = False
        self._last_block_index = -1
        self._last_target_watts = 0
        self._block_transition_from_watts = None
        self._block_transition_elapsed = 0.0
        self._adaptive_low_cadence_sec = 0.0
        self._adaptive_relief_watts = 0.0
        self._reset_metrics()
        self.trainer.start_session()
        return self.snapshot()

    def pause(self) -> TrainingSnapshot:
        if self.state in {"running", "waiting_for_pedal"}:
            self.metrics.break_power_window()
            self.state = "paused"
            self._auto_paused = False
            self._ramping = False
            self.trainer.pause_session()
        return self.snapshot()

    def resume(self) -> TrainingSnapshot:
        if self.state == "paused":
            self._auto_paused = False
            self._zero_watts_sec = 0.0
            self.state = "waiting_for_pedal"
            self.trainer.start_session()
        return self.snapshot()

    def stop(self, status: str = "stopped") -> TrainingSnapshot:
        if self.workout is None:
            return self.snapshot()
        if self.state in {"running", "paused", "waiting_for_pedal"}:
            self.trainer.stop_session()
            self._pending_session = self._build_session(status)
        self.state = "stopped"
        self._ramping = False
        self._auto_paused = False
        self._block_transition_from_watts = None
        return self.snapshot()

    def skip_block(self) -> TrainingSnapshot:
        if self.workout is None or self.state not in {"running", "paused", "waiting_for_pedal"}:
            return self.snapshot()
        current_index, _, _ = self.workout.locate_block(self.elapsed_sec)
        if current_index >= self.workout.total_blocks - 1:
            return self._complete_workout()
        self.elapsed_sec = float(self.workout.block_start_offset(current_index + 1))
        self._update_target_state(0.0)
        return self._apply_control()

    def previous_block(self) -> TrainingSnapshot:
        if self.workout is None or self.state not in {"running", "paused", "waiting_for_pedal"}:
            return self.snapshot()
        current_index, _, _ = self.workout.locate_block(self.elapsed_sec)
        if current_index <= 0:
            self.elapsed_sec = 0.0
        else:
            self.elapsed_sec = float(self.workout.block_start_offset(current_index - 1))
        self._update_target_state(0.0)
        return self._apply_control()

    def adjust_target(self, delta_watts: int) -> TrainingSnapshot:
        if self.state in {"running", "paused", "waiting_for_pedal"}:
            self.adjustment_watts += delta_watts
        return self._apply_control()

    def tick(self, dt: float) -> TrainingSnapshot:
        if self.workout is None:
            return self.snapshot()
        dt = max(0.0, dt)
        probe = self.trainer.read_snapshot()

        if self.state == "running" and (not probe.connected or dt > self.MAX_TICK_GAP_SEC):
            # Never count a disconnected interval or a suspended UI as riding.
            self.metrics.break_power_window()
            self.state = "paused"
            self._auto_paused = dt <= self.MAX_TICK_GAP_SEC
            self._ramping = False
            self._block_transition_from_watts = None
            self.trainer.pause_session()
            return self._apply_control()

        if self.state == "waiting_for_pedal" or (self.state == "paused" and self._auto_paused):
            if probe.connected and probe.current_watts > 0:
                self.state = "running"
                self._auto_paused = False
                self._ramping = True
                self._ramp_elapsed_sec = 0.0
                self._zero_watts_sec = 0.0
                self.trainer.start_session()
                self._update_target_state(0.0)
            return self._apply_control()

        if self.state == "running":
            dt = min(dt, self.workout.total_duration_sec - self.elapsed_sec)
            if probe.current_watts <= 0:
                dt = min(dt, max(0.0, self.ZERO_WATTS_PAUSE_DELAY_SEC - self._zero_watts_sec))
                self._zero_watts_sec += dt
            else:
                self._zero_watts_sec = 0.0
            hr, hr_connected = self._read_hr()
            self.metrics.add(dt, probe.current_watts, probe.cadence,
                             hr if hr_connected else None, self.elapsed_sec, self._target_watts())
            self.elapsed_sec += dt
            self._update_target_state(dt)
            self._update_adaptive_erg(probe.cadence, dt)
            if self.elapsed_sec >= self.workout.total_duration_sec:
                return self._complete_workout()
            if self._zero_watts_sec >= self.ZERO_WATTS_PAUSE_DELAY_SEC:
                self.metrics.break_power_window()
                self.state = "paused"
                self._auto_paused = True
                self._ramping = False
                self._block_transition_from_watts = None
                self.trainer.pause_session()
        return self._apply_control()

    @property
    def pending_session(self) -> WorkoutSessionRecord | None:
        return self._pending_session

    def acknowledge_session(self, session_id: str) -> None:
        if self._pending_session is not None and self._pending_session.id == session_id:
            self._pending_session = None

    def _update_target_state(self, dt: float) -> None:
        if self.workout is None:
            return
        index, _, _ = self.workout.locate_block(self.elapsed_sec)
        if self._ramping:
            self._ramp_elapsed_sec += dt
            if self._ramp_elapsed_sec >= self.RAMP_DURATION_SEC:
                self._ramping = False
        if self._block_transition_from_watts is not None:
            self._block_transition_elapsed += dt
            if self._block_transition_elapsed >= self.BLOCK_TRANSITION_SEC:
                self._block_transition_from_watts = None
        if self.state == "running" and self._last_block_index >= 0 and index != self._last_block_index:
            self._block_transition_from_watts = self._last_target_watts
            self._block_transition_elapsed = 0.0
            self._adaptive_low_cadence_sec = 0.0
            self._adaptive_relief_watts = 0.0
        self._last_block_index = index
        self._last_target_watts = self._target_watts()

    def _target_watts(self) -> int:
        if self.workout is None:
            return 0
        _, block, seconds_in_block = self.workout.locate_block(self.elapsed_sec)
        target = max(0, min(32767, block.target_watts_at(seconds_in_block) + self.adjustment_watts))
        if self._block_transition_from_watts is not None and not self._ramping:
            progress = min(1.0, self._block_transition_elapsed / self.BLOCK_TRANSITION_SEC)
            target = round(self._block_transition_from_watts + (target - self._block_transition_from_watts) * progress)
        if self._ramping:
            progress = min(1.0, self._ramp_elapsed_sec / self.RAMP_DURATION_SEC)
            target = round(self.RAMP_START_WATTS + (target - self.RAMP_START_WATTS) * progress)
        return target

    def _update_adaptive_erg(self, cadence: int, dt: float) -> None:
        """Relieve ERG resistance gradually when cadence stays below its target."""
        if not self.adaptive_erg or self.workout is None or self.state != "running":
            self._adaptive_low_cadence_sec = 0.0
            self._adaptive_relief_watts = 0.0
            return
        _, block, _ = self.workout.locate_block(self.elapsed_sec)
        target_cadence = block.target_cadence
        target_watts = self._target_watts()
        if not target_cadence or cadence <= 0 or target_watts <= 0:
            self._adaptive_low_cadence_sec = 0.0
            self._adaptive_relief_watts = max(
                0.0, self._adaptive_relief_watts - self.ADAPTIVE_ERG_RECOVERY_RATE_WATTS_PER_SEC * dt
            )
            return

        deficit = target_cadence - cadence - self.ADAPTIVE_ERG_DEADBAND_RPM
        if deficit > 0:
            self._adaptive_low_cadence_sec += dt
            maximum = target_watts * self.ADAPTIVE_ERG_MAX_RELIEF_RATIO
            desired = maximum * min(1.0, deficit / 12.0)
            if self._adaptive_low_cadence_sec >= self.ADAPTIVE_ERG_TRIGGER_SEC:
                self._adaptive_relief_watts = min(
                    desired, self._adaptive_relief_watts + self.ADAPTIVE_ERG_RELIEF_RATE_WATTS_PER_SEC * dt
                )
            return

        self._adaptive_low_cadence_sec = 0.0
        self._adaptive_relief_watts = max(
            0.0, self._adaptive_relief_watts - self.ADAPTIVE_ERG_RECOVERY_RATE_WATTS_PER_SEC * dt
        )

    def _trainer_target_watts(self) -> int:
        target = self._target_watts()
        if self.adaptive_erg:
            target -= round(self._adaptive_relief_watts)
        return max(0, target)

    def _apply_control(self) -> TrainingSnapshot:
        snapshot = self.snapshot()
        self.trainer.update(
            snapshot.trainer_target_watts, snapshot.target_cadence, 0.0, self.state == "running")
        return snapshot

    def _read_hr(self) -> tuple[int, bool]:
        if self.hr_monitor is None:
            return 0, False
        hr_snap = self.hr_monitor.read_snapshot()
        return hr_snap.heart_rate, hr_snap.connected

    def snapshot(self) -> TrainingSnapshot:
        hr, hr_connected = self._read_hr()
        if self.workout is None:
            return TrainingSnapshot(
                state="idle",
                workout_name="Kein Workout geladen",
                elapsed_sec=0,
                remaining_sec=0,
                current_block_name="-",
                block_index=0,
                block_count=0,
                current_watts=0,
                current_cadence=0,
                target_watts=0,
                target_cadence=None,
                target_pct_label=None,
                adjustment_watts=0,
                zone_label="-",
                trainer_label=self.trainer.mode_label,
                trainer_connected=self.trainer.ready_for_workout(),
                heart_rate=hr,
                hr_connected=hr_connected,
            )

        index, block, _ = self.workout.locate_block(self.elapsed_sec)
        target_watts = self._target_watts()
        trainer_target_watts = self._trainer_target_watts()
        target_cadence = block.target_cadence
        trainer_snapshot = self.trainer.read_snapshot()
        zone = power_zone_for_watts(target_watts, self.workout.ftp_watts)
        target_pct = target_watts / self.workout.ftp_watts if self.workout.ftp_watts > 0 else None
        target_pct_label = f"{round(target_pct * 100)}% FTP" if target_pct is not None else None
        return TrainingSnapshot(
            state=self.state,
            active_sec=round(self.metrics.active_seconds),
            workout_name=self.workout.name,
            elapsed_sec=round(self.elapsed_sec),
            remaining_sec=max(0, self.workout.total_duration_sec - round(self.elapsed_sec)),
            current_block_name=block.label,
            block_index=index,
            block_count=self.workout.total_blocks,
            current_watts=trainer_snapshot.current_watts,
            current_cadence=trainer_snapshot.cadence,
            target_watts=target_watts,
            target_cadence=target_cadence,
            target_pct_label=target_pct_label,
            adjustment_watts=self.adjustment_watts,
            zone_label=zone.label,
            trainer_label=trainer_snapshot.source_label,
            trainer_connected=trainer_snapshot.connected,
            heart_rate=hr,
            hr_connected=hr_connected,
            auto_paused=self._auto_paused,
            ramping=self._ramping,
            trainer_target_watts=trainer_target_watts,
            adaptive_erg=self.adaptive_erg,
            adaptive_relief_watts=round(self._adaptive_relief_watts),
            **self.metrics.summary(self.workout.ftp_watts),
        )

    @property
    def is_ftp_test(self) -> bool:
        if self.workout is None:
            return False
        name = self.workout.name.lower()
        return "ftp" in name and "ramp" in name

    def best_1min_avg_watts(self) -> int:
        """Best complete 60-second window on a one-second power series."""
        if self.is_ftp_test:
            return (self._ftp_result() or {}).get("best_minute_watts", 0)
        return round(self.metrics.best_minute)

    def calculate_ftp_from_ramp(self) -> int:
        """FTP = 75% of best 1-minute average power (standard ramp test protocol)."""
        return (self._ftp_result() or {}).get("estimated_ftp", 0)

    def _ftp_result(self) -> dict | None:
        from cados.core.session_analysis import ftp_test_result
        if self.workout is None:
            return None
        return ftp_test_result({"workout_name": self.workout.name, "ftp_watts": self.workout.ftp_watts,
            "workout_payload": self.workout_template.to_dict(), "samples": self.metrics.samples})

    def _complete_workout(self) -> TrainingSnapshot:
        if self.workout is None or self.state in {"completed", "stopped"}:
            return self.snapshot()
        self.elapsed_sec = float(self.workout.total_duration_sec)
        self.state = "completed"
        self.trainer.stop_session()
        if self._pending_session is None:
            self._pending_session = self._build_session("completed")
        return self.snapshot()

    def _build_session(self, status: str) -> WorkoutSessionRecord:
        if self.workout is None:
            raise ValueError("No workout loaded.")
        profile = self.profile or UserProfile(name="Standard", ftp=self.workout.ftp_watts)
        workout_payload = self.workout_template.to_dict() if self.workout_template is not None else self.workout.to_dict()
        return WorkoutSessionRecord(
            ftp_test_result=self._ftp_result(),
            user_id=profile.id,
            user_name=profile.name,
            workout_name=self.workout.name,
            workout_file_name=self.workout.source_path.name,
            workout_payload=workout_payload,
            duration_sec=round(self.metrics.active_seconds),
            workout_elapsed_sec=round(self.elapsed_sec),
            ftp_watts=self.workout.ftp_watts,
            started_at=self.started_at,
            metrics=self.metrics.summary(self.workout.ftp_watts),
            samples=[dict(sample) for sample in self.metrics.samples],
            status=status,
            trainer_source=self.trainer.mode_label.lower().replace(" ", "_"),
        )
