import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cados.models.session import WorkoutSessionRecord
from cados.services.storage import DataStore, LocalJsonStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.store = LocalJsonStore(root / "profiles.json", root / "sessions.json")

    def session(self):
        return WorkoutSessionRecord(user_id="test", user_name="Tester", workout_name="Test",
                                    duration_sec=10, status="stopped", trainer_source="fake",
                                    ftp_watts=250, started_at="2026-01-01T12:00:00+00:00",
                                    workout_elapsed_sec=60, metrics={"avg_watts": 200},
                                    samples=[{"duration_sec": 10, "watts": 200, "heart_rate": 140}])

    def test_new_fields_survive_save_reload_and_retry_without_duplicates(self):
        session = self.session()
        self.store.save_session(session)
        self.store.save_session(session)
        records = self.store.list_sessions()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].to_dict(), session.to_dict())

    def test_legacy_sessions_remain_readable(self):
        old = self.session().to_dict()
        for key in ["ftp_watts", "started_at", "workout_elapsed_sec", "metrics", "samples"]:
            old.pop(key)
        self.store.sessions_path.write_text(json.dumps([old]))
        session = self.store.list_sessions()[0]
        self.assertEqual(session.duration_sec, 10)
        self.assertIsNone(session.ftp_watts)
        self.assertEqual(session.samples, [])

    def test_corrupt_file_is_not_overwritten(self):
        self.store.sessions_path.write_text("[broken")
        with self.assertRaises(ValueError):
            self.store.save_session(self.session())
        self.assertEqual(self.store.sessions_path.read_text(), "[broken")

    def test_mirror_failure_does_not_fail_local_session_save(self):
        store = DataStore(self.store.profiles_path, self.store.sessions_path, None)
        with patch.object(store.postgres, "save_session", side_effect=OSError("database offline")):
            with self.assertLogs("cados.services.storage", level="ERROR"):
                store.save_session(self.session())
        self.assertEqual(len(store.local.list_sessions()), 1)
