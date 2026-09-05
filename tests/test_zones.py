from __future__ import annotations

import unittest
from pathlib import Path

from cados.core.zones import power_zone_for_watts, split_block_into_zone_segments, summarize_workout_zones
from cados.models.workout import ResolvedWorkout, ResolvedWorkoutBlock


class PowerZoneTests(unittest.TestCase):
    def test_power_zone_uses_ftp_ranges(self) -> None:
        self.assertEqual(power_zone_for_watts(150, 250).label, "Z2 Endurance")
        self.assertEqual(power_zone_for_watts(225, 250).label, "Z3 Tempo")
        self.assertEqual(power_zone_for_watts(320, 250).label, "Z6 Anaerobic")

    def test_workout_zone_summary_splits_ramp_across_multiple_zones(self) -> None:
        workout = ResolvedWorkout(
            name="Zone Summary",
            description="",
            author="Cados",
            ftp_reference=None,
            ftp_watts=200,
            blocks=(
                ResolvedWorkoutBlock(kind="steady", label="Endurance", duration_sec=60, target_watts=140),
                ResolvedWorkoutBlock(kind="ramp", label="Build", duration_sec=20, start_watts=140, end_watts=220),
            ),
            source_path=Path("zone_summary.json"),
        )

        summary = summarize_workout_zones(workout)
        by_zone = {entry.zone.label: entry for entry in summary}

        self.assertEqual(by_zone["Z2 Endurance"].duration_sec, 63)
        self.assertEqual(by_zone["Z3 Tempo"].duration_sec, 8)
        self.assertEqual(by_zone["Z4 Threshold"].duration_sec, 8)
        self.assertEqual(by_zone["Z5 VO2 Max"].duration_sec, 3)
        self.assertEqual(by_zone["Z2 Endurance"].watt_range_label, "111-150 W")
        self.assertAlmostEqual(by_zone["Z2 Endurance"].percentage, 78.125, places=3)

    def test_block_segments_follow_zone_boundaries(self) -> None:
        block = ResolvedWorkoutBlock(kind="ramp", label="Build", duration_sec=20, start_watts=140, end_watts=220)

        segments = split_block_into_zone_segments(block, 200)

        self.assertEqual([segment.zone.label for segment in segments], ["Z2 Endurance", "Z3 Tempo", "Z4 Threshold", "Z5 VO2 Max"])
        self.assertAlmostEqual(segments[0].start_progress, 0.0, places=4)
        self.assertAlmostEqual(segments[0].end_progress, 0.125, places=4)
        self.assertAlmostEqual(segments[-1].start_watts, 210.0, places=4)
        self.assertAlmostEqual(segments[-1].end_watts, 220.0, places=4)


if __name__ == "__main__":
    unittest.main()
