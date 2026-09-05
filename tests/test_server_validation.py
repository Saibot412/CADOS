import unittest

from server.app.validation import validate_source_name, validate_workout_payload


class ServerValidationTests(unittest.TestCase):
    def test_accepts_valid_workout(self):
        payload = {"name": "Valid", "blocks": [{
            "type": "steady", "duration_sec": 60, "target_pct_ftp": 0.8,
        }]}
        self.assertIs(validate_workout_payload(payload), payload)

    def test_rejects_invalid_payload(self):
        for payload in [{}, {"name": "x", "blocks": []},
                        {"name": "x", "blocks": [{"type": "free", "duration_sec": 60}]}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_workout_payload(payload)

    def test_normalizes_source_name(self):
        self.assertEqual(validate_source_name("folder/My Workout.zwo"), "My Workout.zwo.json")
