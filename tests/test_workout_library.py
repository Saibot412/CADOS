import io
import json
import unittest
from unittest.mock import patch

from cados.services.workout_library import WorkoutLibraryClient, WorkoutLibraryError


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.payload


class WorkoutLibraryClientTests(unittest.TestCase):
    def test_requires_https_for_remote_servers(self):
        client = WorkoutLibraryClient("http://example.com", "secret")
        with self.assertRaises(WorkoutLibraryError):
            client.list_workouts()

    def test_reads_workouts_and_sends_bearer_token(self):
        payload = {"name": "Remote", "blocks": [{"type": "steady", "duration_sec": 60, "target_watts": 100}]}
        response = Response({"records": [{"id": "1", "kind": "workout", "revision": 2, "payload": payload}]})
        with patch("cados.services.workout_library.urlopen", return_value=response) as request:
            items = WorkoutLibraryClient("https://example.com", "top-secret").list_workouts()
        self.assertEqual(items[0].payload, payload)
        sent = request.call_args.args[0]
        self.assertEqual(sent.get_header("Authorization"), "Bearer top-secret")

    def test_rejects_invalid_response_shape(self):
        with patch("cados.services.workout_library.urlopen", return_value=Response({"wrong": []})):
            with self.assertRaises(WorkoutLibraryError):
                WorkoutLibraryClient("https://example.com", "secret").list_workouts()
