import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord
from cados.services.storage import DataStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = DataStore(self.root / "cados.sqlite3")

    def session(self):
        return WorkoutSessionRecord(
            user_id="test", user_name="Tester", workout_name="Test",
            duration_sec=10, status="stopped", trainer_source="fake",
            ftp_watts=250, started_at="2026-01-01T12:00:00+00:00",
            workout_elapsed_sec=60, metrics={"avg_watts": 200},
            samples=[{"duration_sec": 10, "watts": 200, "heart_rate": 140}],
        )

    def test_profile_and_session_round_trip_without_duplicates(self):
        profile = UserProfile(name="Tester", ftp=250)
        self.store.save_profile(profile)
        self.store.save_profile(profile)
        session = self.session()
        self.store.save_session(session)
        self.store.save_session(session)
        self.assertEqual([item.to_dict() for item in self.store.list_profiles()], [profile.to_dict()])
        self.assertEqual([item.to_dict() for item in self.store.list_sessions()], [session.to_dict()])

    def test_samples_are_kept_separately_and_can_be_omitted(self):
        session = self.session()
        self.store.save_session(session)
        with self.store.connection() as connection:
            payload = json.loads(connection.execute("SELECT payload FROM sessions").fetchone()["payload"])
            self.assertNotIn("samples", payload)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM session_samples").fetchone()[0], 1)
        self.assertEqual(self.store.list_sessions(include_samples=False)[0].samples, [])

    def test_planned_workouts_round_trip_and_can_be_removed(self):
        payload = {"workout_id": "workout-1", "workout_name": "Intervalle", "date": "2026-09-13"}
        self.store.save_plan("plan-1", payload)
        self.assertEqual(self.store.list_plans("2026-09-13"), [{"id": "plan-1", **payload}])
        self.store.delete_plan("plan-1")
        self.assertEqual(self.store.list_plans(), [])

    def test_legacy_json_migration_is_atomic_and_runs_once(self):
        profiles = self.root / "profiles.json"
        sessions = self.root / "sessions.json"
        profile = UserProfile(name="Alt", ftp=220)
        session = self.session()
        profiles.write_text(json.dumps([profile.to_dict()]))
        sessions.write_text(json.dumps([session.to_dict()]))
        self.assertEqual(self.store.migrate_legacy_json(profiles, sessions), {"profiles": 1, "sessions": 1})
        self.assertEqual(self.store.migrate_legacy_json(profiles, sessions), {"profiles": 0, "sessions": 0})
        self.assertTrue(profiles.exists())
        self.assertTrue(sessions.exists())

    def test_corrupt_legacy_json_does_not_mark_migration_done(self):
        profiles = self.root / "profiles.json"
        sessions = self.root / "sessions.json"
        profiles.write_text("[broken")
        sessions.write_text("[]")
        with self.assertRaises(ValueError):
            self.store.migrate_legacy_json(profiles, sessions)
        self.assertFalse(self.store.migration_done("legacy_profiles_sessions_v1"))

    def test_workouts_deduplicate_by_content_and_update_by_source(self):
        first = {"name": "One", "blocks": [{"type": "steady", "duration_sec": 60, "target_watts": 100}]}
        second = {"name": "Two", "blocks": [{"type": "steady", "duration_sec": 60, "target_watts": 120}]}
        identifier = self.store.save_workout(first, "same.json")
        self.assertEqual(self.store.save_workout(first, "copy.json"), identifier)
        self.assertEqual(self.store.save_workout(second, "same.json"), identifier)
        self.assertEqual(len(self.store.list_workouts()), 1)
        self.assertEqual(self.store.list_workouts()[0]["payload"]["name"], "Two")

    def test_backup_is_a_valid_independent_database(self):
        self.store.save_profile(UserProfile(name="Backup", ftp=250))
        backup = self.root / "backup.sqlite3"
        self.store.backup(backup)
        reopened = DataStore(backup)
        self.assertEqual(reopened.list_profiles()[0].name, "Backup")
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
