from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cados.core.workout_loader import WorkoutLoader, WorkoutValidationError
from cados.models.workout import DEFAULT_FTP_WATTS


class WorkoutLoaderTests(unittest.TestCase):
    def test_loads_template_and_resolves_pct_with_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workouts_dir = Path(temp_dir)
            workout_path = workouts_dir / "sample.json"
            workout_path.write_text(
                json.dumps(
                    {
                        "name": "Loader Test",
                        "description": "Test workout",
                        "author": "Cados",
                        "blocks": [
                            {
                                "type": "steady",
                                "label": "Tempo",
                                "duration_sec": 300,
                                "target_pct_ftp": 0.88,
                                "target_watts": 300,
                                "target_cadence": 90,
                            },
                            {
                                "type": "ramp",
                                "label": "Ramp",
                                "duration_sec": 120,
                                "start_pct_ftp": 0.50,
                                "end_pct_ftp": 0.80,
                                "start_watts": 180,
                                "end_watts": 220,
                                "target_cadence": 92,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            loader = WorkoutLoader(workouts_dir)
            workouts = loader.scan()

        self.assertEqual(len(workouts), 1)
        template = workouts[0]
        resolved = template.resolve(250)
        self.assertEqual(template.total_duration_sec, 420)
        self.assertEqual(resolved.blocks[0].target_watts_at(0), 220)
        self.assertEqual(resolved.blocks[1].target_watts_at(60), 162)

    def test_uses_default_ftp_when_no_profile_or_reference_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workouts_dir = Path(temp_dir)
            workout_path = workouts_dir / "fallback.json"
            workout_path.write_text(
                json.dumps(
                    {
                        "name": "Fallback FTP",
                        "blocks": [
                            {
                                "type": "steady",
                                "duration_sec": 60,
                                "target_pct_ftp": 0.75,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            loader = WorkoutLoader(workouts_dir)
            template = loader.scan()[0]

        resolved = template.resolve(None, default_ftp_watts=DEFAULT_FTP_WATTS)
        self.assertEqual(resolved.ftp_watts, DEFAULT_FTP_WATTS)
        self.assertEqual(resolved.blocks[0].target_watts, 150)

    def test_scan_skips_invalid_numbers_and_still_loads_valid_workouts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, value in enumerate(["invalid", {}, True, 1.5, float("inf")]):
                payload = {"name": "Bad", "blocks": [{"type": "steady", "duration_sec": value, "target_watts": 100}]}
                (root / f"bad{index}.json").write_text(json.dumps(payload))
            (root / "good.json").write_text(json.dumps({"name": "Good", "blocks": [
                {"type": "steady", "duration_sec": 60, "target_watts": 100}]}))
            with self.assertLogs("cados.core.workout_loader", level="WARNING"):
                workouts = WorkoutLoader(root).scan()
            self.assertEqual([w.name for w in workouts], ["Good"])

    def test_rejects_nonfinite_or_invalid_power_targets(self):
        loader = WorkoutLoader(Path("."))
        for value in [float("nan"), float("inf"), "bad", True, -1, 0]:
            with self.subTest(value=value), self.assertRaises(WorkoutValidationError):
                loader.load_payload({"name": "Bad", "blocks": [
                    {"type": "steady", "duration_sec": 60, "target_pct_ftp": value}]}, Path("bad.json"))


if __name__ == "__main__":
    unittest.main()
