from __future__ import annotations

import unittest
from pathlib import Path

from cados.core.workout_engine import WorkoutEngine
from cados.models.profile import UserProfile
from cados.models.workout import WorkoutTemplate, WorkoutTemplateBlock
from fakes import FakeTrainer, FakeHRMonitor


class WorkoutEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trainer = FakeTrainer()
        self.hr = FakeHRMonitor()
        self.engine = WorkoutEngine(self.trainer, self.hr)
        self.engine.set_profile(UserProfile(name="Tester", ftp=250))

    def tearDown(self) -> None:
        self.trainer.close()

    def _build_workout(self) -> WorkoutTemplate:
        return WorkoutTemplate(
            name="Engine Test",
            description="",
            author="Cados",
            ftp_reference=None,
            blocks=(
                WorkoutTemplateBlock(
                    kind="ramp",
                    label="Ramp",
                    duration_sec=10,
                    start_pct_ftp=0.4,
                    end_pct_ftp=0.8,
                    target_cadence=85,
                ),
                WorkoutTemplateBlock(
                    kind="steady",
                    label="Steady",
                    duration_sec=5,
                    target_pct_ftp=0.88,
                    target_watts=260,
                    target_cadence=95,
                ),
            ),
            source_path=Path("engine_test.json"),
        )

    def test_ramp_target_progresses_linearly(self) -> None:
        self.engine.load_workout(self._build_workout())
        self.engine.start()
        self.engine.tick(0.25)  # Pedaling starts the five-second startup ramp.
        snapshot = self.engine.tick(5.0)

        self.assertEqual(snapshot.target_watts, 150)
        self.assertEqual(snapshot.target_cadence, 85)
        self.assertEqual(snapshot.zone_label, "Z2 Endurance")
        self.assertEqual(snapshot.target_pct_label, "60% FTP")

    def test_same_template_scales_for_different_ftp_values(self) -> None:
        workout = self._build_workout()
        first = workout.resolve(200)
        second = workout.resolve(300)

        self.assertEqual(first.blocks[1].target_watts, 176)
        self.assertEqual(second.blocks[1].target_watts, 264)

    def test_skip_block_jumps_to_next_block(self) -> None:
        self.engine.load_workout(self._build_workout())
        self.engine.start()
        snapshot = self.engine.skip_block()

        self.assertEqual(snapshot.current_block_name, "Steady")
        self.assertEqual(snapshot.target_watts, 220)
        self.assertEqual(snapshot.block_index, 1)

    def test_completed_workout_emits_template_payload_session(self) -> None:
        self.engine.load_workout(self._build_workout())
        self.engine.start()
        self.engine.tick(0.25)
        for _ in range(60):
            snapshot = self.engine.tick(0.25)
        session = self.engine.pending_session

        self.assertEqual(snapshot.state, "completed")
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.status, "completed")
        self.assertEqual(session.duration_sec, 15)
        self.assertEqual(session.workout_payload["blocks"][0]["start_pct_ftp"], 0.4)

    def _start_riding(self):
        self.engine.load_workout(self._build_workout())
        self.engine.start()
        self.engine.tick(0.25)

    def test_waits_for_pedal_without_counting_time(self):
        self.trainer.telemetry.current_watts = 0
        self.engine.load_workout(self._build_workout())
        self.engine.start()
        self.assertEqual(self.engine.tick(1).state, "waiting_for_pedal")
        self.assertEqual(self.engine.metrics.active_seconds, 0)

    def test_auto_pause_and_resume_with_ramp(self):
        self._start_riding()
        self.engine.tick(1)
        self.trainer.telemetry.current_watts = 0
        self.assertEqual(self.engine.tick(1).state, "running")
        paused = self.engine.tick(1)
        self.assertTrue(paused.auto_paused)
        self.assertEqual(paused.state, "paused")
        active_time = self.engine.metrics.active_seconds
        self.engine.tick(2)
        self.assertEqual(self.engine.metrics.active_seconds, active_time)
        self.trainer.telemetry.current_watts = 200
        resumed = self.engine.tick(0.25)
        self.assertEqual(resumed.state, "running")
        self.assertEqual(resumed.target_watts, 30)
        self.assertTrue(resumed.ramping)

    def test_manual_pause_does_not_auto_resume(self):
        self._start_riding()
        self.engine.pause()
        self.assertEqual(self.engine.tick(1).state, "paused")
        self.engine.resume()
        self.assertEqual(self.engine.tick(0.25).state, "running")

    def test_adaptive_erg_relaxes_after_sustained_low_cadence_and_recovers(self):
        self.engine.set_adaptive_erg(True)
        workout = WorkoutTemplate(
            name="Adaptive", description="", author="Cados", ftp_reference=None,
            blocks=(WorkoutTemplateBlock(kind="steady", label="Steady", duration_sec=60,
                                         target_watts=300, target_cadence=90),),
            source_path=Path("adaptive.json"),
        )
        self.engine.load_workout(workout)
        self.engine.start()
        self.engine.tick(0.25)
        self.engine.tick(5)
        target = self.engine.snapshot().target_watts
        self.trainer.telemetry.cadence = 70
        for _ in range(12):
            snapshot = self.engine.tick(0.5)
        self.assertTrue(snapshot.adaptive_erg)
        self.assertGreater(snapshot.adaptive_relief_watts, 0)
        self.assertLess(snapshot.trainer_target_watts, target)
        self.assertGreaterEqual(snapshot.trainer_target_watts, round(target * 0.9))
        self.trainer.telemetry.cadence = 100
        for _ in range(20):
            snapshot = self.engine.tick(0.5)
        self.assertEqual(snapshot.adaptive_relief_watts, 0)
        self.assertEqual(snapshot.trainer_target_watts, snapshot.target_watts)

    def test_normal_erg_keeps_the_exact_target_when_cadence_is_low(self):
        self._start_riding()
        self.trainer.telemetry.cadence = 60
        for _ in range(12):
            snapshot = self.engine.tick(0.5)
        self.assertFalse(snapshot.adaptive_erg)
        self.assertEqual(snapshot.trainer_target_watts, snapshot.target_watts)

    def test_erg_mode_can_be_switched_during_a_workout(self):
        self._start_riding()
        self.engine.set_adaptive_erg(True)
        self.assertTrue(self.engine.snapshot().adaptive_erg)
        self.engine.set_adaptive_erg(False)
        snapshot = self.engine.snapshot()
        self.assertFalse(snapshot.adaptive_erg)
        self.assertEqual(snapshot.trainer_target_watts, snapshot.target_watts)

    def test_disconnect_and_reconnect_do_not_count_missing_time(self):
        self._start_riding()
        self.engine.tick(1)
        self.trainer.telemetry.connected = False
        self.assertEqual(self.engine.tick(1).state, "paused")
        self.engine.tick(1)
        self.assertEqual(self.engine.metrics.active_seconds, 1)
        self.trainer.telemetry.connected = True
        self.assertEqual(self.engine.tick(0.25).state, "running")

    def test_suspend_gap_is_not_recorded_as_riding(self):
        self._start_riding()
        self.engine.tick(1)
        self.assertEqual(self.engine.tick(120).state, "paused")
        self.assertEqual(self.engine.metrics.active_seconds, 1)

    def test_block_navigation_does_not_change_ridden_duration(self):
        self._start_riding()
        self.engine.tick(2)
        self.engine.skip_block()
        self.engine.previous_block()
        self.engine.tick(1)
        self.engine.stop()
        session = self.engine.pending_session
        self.assertEqual(session.duration_sec, 3)
        self.assertEqual(session.workout_elapsed_sec, 1)

    def test_snapshot_has_no_commands_or_state_changes(self):
        self._start_riding()
        self.engine.tick(1)
        commands = list(self.trainer.commands)
        state = dict(vars(self.engine))
        first = self.engine.snapshot()
        self.assertEqual(first, self.engine.snapshot())
        self.assertEqual(self.trainer.commands, commands)
        self.assertEqual(vars(self.engine), state)

    def test_session_contains_metrics_samples_ftp_and_start(self):
        self._start_riding()
        self.engine.tick(2)
        self.engine.stop()
        session = self.engine.pending_session
        self.assertEqual(session.ftp_watts, 250)
        self.assertEqual(session.started_at, self.engine.started_at)
        self.assertEqual(session.metrics["avg_watts"], 200)
        self.assertEqual(session.metrics["avg_heart_rate"], 140)
        self.assertEqual(session.samples[0]["watts"], 200)

    def test_pending_session_is_retained_until_acknowledged(self):
        self._start_riding()
        self.engine.tick(1)
        self.engine.stop()
        session = self.engine.pending_session
        self.engine.stop()
        self.assertIs(self.engine.pending_session, session)
        self.engine.acknowledge_session("wrong-id")
        self.assertIs(self.engine.pending_session, session)
        with self.assertRaises(ValueError):
            self.engine.load_workout(self._build_workout())
        self.engine.acknowledge_session(session.id)
        self.assertIsNone(self.engine.pending_session)
        self.engine.load_workout(self._build_workout())

    def test_completion_clamps_last_tick_and_does_not_duplicate_session(self):
        self._start_riding()
        for _ in range(4):
            self.engine.tick(3.7)
        self.engine.tick(1)
        session = self.engine.pending_session
        self.assertEqual(session.duration_sec, 15)
        self.assertAlmostEqual(self.engine.metrics.active_seconds, 15)
        self.engine.acknowledge_session(session.id)
        self.engine.skip_block()
        self.engine.tick(1)
        self.assertIsNone(self.engine.pending_session)


if __name__ == "__main__":
    unittest.main()


class FTPCadenceFinishTests(unittest.TestCase):
    setUp = WorkoutEngineTests.setUp
    tearDown = WorkoutEngineTests.tearDown
    _build_workout = WorkoutEngineTests._build_workout
    def _start_test(self):
        from dataclasses import replace
        template = replace(self._build_workout(), name="FTP Ramp Test", blocks=(
            WorkoutTemplateBlock(kind="steady", label="Warmup", duration_sec=10, target_watts=150),
            WorkoutTemplateBlock(kind="steady", label="Step 1", duration_sec=120, target_watts=300),
            WorkoutTemplateBlock(kind="steady", label="Cooldown", duration_sec=30, target_watts=100),
        ))
        self.engine.load_workout(template)
        self.engine.start()
        self.engine.tick(.25)

    def test_zero_cadence_finishes_and_evaluates_actual_test_time(self):
        self._start_test()
        self.engine.skip_block()
        self.trainer.telemetry.current_watts = 300
        for _ in range(60):
            self.engine.tick(1)
        elapsed = self.engine.elapsed_sec
        self.trainer.telemetry.cadence = 0
        self.engine.tick(.25)
        session = self.engine.pending_session
        self.assertEqual(self.engine.state, "completed")
        self.assertEqual(session.workout_elapsed_sec, elapsed)
        self.assertEqual(session.ftp_test_result["estimated_ftp"], 225)
        self.assertIn(("stop",), self.trainer.commands)
        self.engine.tick(1)
        self.assertIs(self.engine.pending_session, session)

    def test_zero_without_previous_stage_cadence_does_not_finish(self):
        self._start_test()
        self.engine.skip_block()
        self.trainer.telemetry.cadence = 0
        self.engine.tick(1)
        self.assertEqual(self.engine.state, "running")

    def test_warmup_and_disconnect_do_not_finish_test(self):
        self._start_test()
        self.trainer.telemetry.cadence = 0
        self.engine.tick(1)
        self.assertEqual(self.engine.state, "running")
        self.engine.skip_block()
        self.trainer.telemetry.cadence = 90
        self.engine.tick(1)
        self.trainer.telemetry.connected = False
        self.trainer.telemetry.cadence = 0
        self.engine.tick(1)
        self.assertEqual(self.engine.state, "paused")
        self.assertIsNone(self.engine.pending_session)

    def test_regular_workout_keeps_running_at_zero_cadence(self):
        self.engine.load_workout(self._build_workout())
        self.engine.start()
        self.engine.tick(.25)
        self.engine.tick(1)
        self.trainer.telemetry.cadence = 0
        self.engine.tick(1)
        self.assertEqual(self.engine.state, "running")


    def test_missing_cadence_does_not_end_ftp_test(self):
        self._start_test()
        self.engine.skip_block()
        self.engine.tick(1)
        self.trainer.telemetry.cadence = 0
        self.trainer.telemetry.cadence_available = False
        self.engine.tick(1)
        self.assertEqual(self.engine.state, 'running')
