import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication
    from cados.ui.main_window import MainWindow
except ImportError:
    QApplication = None

from cados.config import AppConfig
from cados.services.storage import DataStore
from cados.services.workout_catalog import WorkoutCatalog
from cados.models.session import WorkoutSessionRecord
from fakes import FakeHRMonitor, FakeTrainer


@unittest.skipIf(QApplication is None, "PySide6 is required for UI tests")
class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        config = AppConfig.load(Path(self.directory.name))
        config.paths.bundled_workouts_dir.mkdir(parents=True, exist_ok=True)
        (config.paths.bundled_workouts_dir / "test.json").write_text(json.dumps({
            "name": "Test", "blocks": [{"type": "steady", "duration_sec": 60, "target_watts": 200}]}))
        self.store = DataStore(config.paths.database_path)
        catalog = WorkoutCatalog(config.paths.bundled_workouts_dir, self.store)
        self.trainer = FakeTrainer()
        with patch("cados.ui.main_window.HRMonitorService", FakeHRMonitor):
            self.window = MainWindow(config, catalog, self.store, self.trainer)
        for timer in [self.window.timer, self.window.reconnect_timer, self.window.hr_reconnect_timer]:
            timer.stop()
        self.addCleanup(self.window.shutdown)
        self.window._start_selected_workout()
        self.window.engine.tick(0.25)
        self.window.engine.tick(2)

    def test_close_saves_active_training_before_disconnecting(self):
        event = QCloseEvent()
        self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].duration_sec, 2)
        self.assertEqual(sessions[0].metrics["avg_watts"], 200)
        self.assertEqual(sessions[0].samples[0]["heart_rate"], 140)
        self.assertLess(self.trainer.commands.index(("stop",)), self.trainer.commands.index(("close",)))

    def test_sync_does_not_start_during_training(self):
        with patch("cados.ui.main_window.threading.Thread") as thread:
            self.window._start_library_worker("auto")
            thread.assert_not_called()
        self.assertFalse(self.window._library_request_in_progress)

    def test_deleted_template_can_be_repeated_from_history_payload(self):
        session=WorkoutSessionRecord(user_id="test",user_name="Test",workout_name="Archived",
            duration_sec=60,status="completed",trainer_source="test",workout_file_name="removed.json",
            workout_payload={"name":"Archived","blocks":[{"type":"steady","duration_sec":60,"target_watts":150}]})
        restored=self.window._workout_from_session(session)
        self.assertEqual(restored.name,"Archived")

    def test_close_failure_retains_session_and_a_second_close_retries(self):
        event = QCloseEvent()
        with patch.object(self.store, "save_session", side_effect=OSError("disk full")):
            with patch("cados.ui.main_window.QMessageBox.critical"):
                with self.assertLogs("cados.ui.main_window", level="ERROR"):
                    self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        session = self.window.engine.pending_session
        self.assertIsNotNone(session)
        self.assertFalse(self.window._shutting_down)
        retry = QCloseEvent()
        self.window.closeEvent(retry)
        self.assertTrue(retry.isAccepted())
        self.assertEqual([s.id for s in self.store.list_sessions()], [session.id])

    def test_quit_hook_saves_without_a_window_close_event(self):
        self.window.shutdown()
        self.window.shutdown()
        self.assertEqual(len(self.store.list_sessions()), 1)

    def test_training_ui_renders_updated_metrics(self):
        snapshot = self.window.engine.snapshot()
        self.window._apply_training_snapshot(snapshot)
        self.assertEqual(self.window.current_watts_value.text(), "200 W")
        self.assertEqual(self.window.engine.snapshot(), snapshot)
