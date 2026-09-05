import json
import tempfile
import unittest
from pathlib import Path

from cados.core.workout_loader import WorkoutValidationError
from cados.core.zwo_importer import ZwoImportError
from cados.services.storage import DataStore
from cados.services.workout_catalog import WorkoutCatalog
from cados.services.workout_library import RemoteWorkout


class WorkoutCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.bundled = self.root / "bundled"
        self.bundled.mkdir()
        self.store = DataStore(self.root / "cados.sqlite3")
        self.catalog = WorkoutCatalog(self.bundled, self.store)

    def test_imports_cados_json_into_sqlite(self):
        source = self.root / "own.json"
        source.write_text(json.dumps({
            "name": "Eigenes Training",
            "blocks": [{"type": "steady", "duration_sec": 60, "target_pct_ftp": 0.8}],
        }))
        imported = self.catalog.import_file(source)
        source.unlink()
        self.assertEqual(imported.name, "Eigenes Training")
        self.assertEqual(self.catalog.scan()[0].name, "Eigenes Training")

    def test_imports_standard_zwo_blocks_and_expands_intervals(self):
        source = self.root / "zwift.zwo"
        source.write_text("""<?xml version="1.0"?>
          <workout_file><author>Coach</author><name>ZWO Test</name>
          <description>Training</description><sportType>bike</sportType><workout>
          <Warmup Duration="60" PowerLow="0.4" PowerHigh="0.7" Cadence="90"/>
          <SteadyState Duration="120" Power="0.8"/>
          <IntervalsT Repeat="2" OnDuration="30" OffDuration="20"
            OnPower="1.2" OffPower="0.5" CadenceHigh="100" CadenceResting="85"/>
          <Cooldown Duration="60" PowerLow="0.4" PowerHigh="0.65"/>
          </workout></workout_file>""")
        workout = self.catalog.import_file(source)
        self.assertEqual(workout.name, "ZWO Test")
        self.assertEqual(len(workout.blocks), 7)
        self.assertEqual(workout.total_duration_sec, 340)
        self.assertEqual(workout.blocks[2].target_cadence, 100)
        self.assertEqual(workout.blocks[3].target_cadence, 85)
        self.assertEqual(workout.blocks[-1].start_pct_ftp, 0.65)
        self.assertEqual(workout.blocks[-1].end_pct_ftp, 0.4)

    def test_rejects_unsafe_or_unsupported_zwo(self):
        source = self.root / "bad.zwo"
        for content in [
            '<!DOCTYPE x [<!ENTITY y "bad">]><workout_file/>',
            '<workout_file><sportType>run</sportType><workout><SteadyState Duration="60" Power="1"/></workout></workout_file>',
            '<workout_file><workout><FreeRide Duration="60"/></workout_file>',
            '<workout_file><workout><SteadyState Duration="60" Power="250"/></workout></workout_file>',
        ]:
            source.write_text(content)
            with self.subTest(content=content), self.assertRaises((ZwoImportError, WorkoutValidationError)):
                self.catalog.import_file(source)

    def test_server_workout_overrides_bundled_file_with_same_name(self):
        bundled = {
            "name": "Bundled", "blocks": [{"type": "steady", "duration_sec": 60, "target_watts": 100}]
        }
        (self.bundled / "same.json").write_text(json.dumps(bundled))
        remote = dict(bundled)
        remote["name"] = "Server Version"
        self.catalog.save_remote(RemoteWorkout("remote-1", "same.json", 2, remote))
        workouts = self.catalog.scan()
        self.assertEqual(len(workouts), 1)
        self.assertEqual(workouts[0].name, "Server Version")
