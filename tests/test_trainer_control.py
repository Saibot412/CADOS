import threading
import time
import unittest

from cados.services.trainer import TrainerController, TrainerSnapshot


class BlockingBluetooth:
    connected = True
    available = True

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.changed = threading.Condition()
        self.calls = []
        self.failures = 0

    def _record(self, *call):
        with self.changed:
            self.calls.append(call)
            self.changed.notify_all()

    def start_session(self):
        self._record("start")
        return True

    def pause_session(self):
        self._record("pause")
        return True

    def stop_session(self):
        self._record("stop")
        return True

    def set_target_power(self, watts):
        self._record("power", watts)
        self.entered.set()
        if not self.release.wait(timeout=2):
            return False
        if self.failures:
            self.failures -= 1
            return False
        return True

    def read_snapshot(self):
        return TrainerSnapshot(connected=self.connected)

    def close(self):
        pass

    def wait_for(self, predicate):
        with self.changed:
            return self.changed.wait_for(lambda: predicate(self.calls), timeout=2)


class TrainerControlTests(unittest.TestCase):
    def setUp(self):
        self.bluetooth = BlockingBluetooth()
        self.controller = TrainerController(bluetooth=self.bluetooth, retry_sec=0.02)

    def tearDown(self):
        self.bluetooth.release.set()
        self.controller.close()

    def test_ui_calls_return_while_ble_command_is_blocked(self):
        self.controller.start_session()
        self.controller.update(200, None, 0.25, True)
        self.assertTrue(self.bluetooth.entered.wait(timeout=2))
        started = time.monotonic()
        for watts in range(201, 251):
            self.controller.update(watts, None, 0.25, True)
        self.controller.pause_session()
        self.assertLess(time.monotonic() - started, 0.2)
        self.bluetooth.release.set()
        self.assertTrue(self.bluetooth.wait_for(lambda calls: ("pause",) in calls))
        # Intermediate targets are coalesced, and pause supersedes pending power.
        self.assertEqual([c for c in self.bluetooth.calls if c[0] == "power"], [("power", 200)])

    def test_failed_target_is_retried_without_a_target_change(self):
        self.bluetooth.failures = 1
        self.bluetooth.release.set()
        self.controller.start_session()
        self.controller.update(200, None, 0.25, True)
        self.assertTrue(self.bluetooth.wait_for(lambda calls: calls.count(("power", 200)) == 2))

    def test_reconnection_resends_session_and_target(self):
        self.bluetooth.release.set()
        self.controller.start_session()
        self.controller.update(200, None, 0.25, True)
        self.assertTrue(self.bluetooth.wait_for(lambda calls: ("power", 200) in calls))
        self.bluetooth.connected = False
        self.controller.update(200, None, 0.25, True)
        self.bluetooth.connected = True
        self.controller.update(200, None, 0.25, True)
        self.assertTrue(self.bluetooth.wait_for(lambda calls: calls.count(("power", 200)) == 2))
        self.assertEqual(self.bluetooth.calls.count(("start",)), 2)

    def test_close_stops_an_active_session(self):
        self.bluetooth.release.set()
        self.controller.start_session()
        self.assertTrue(self.bluetooth.wait_for(lambda calls: ("start",) in calls))
        self.controller.close()
        self.assertIn(("stop",), self.bluetooth.calls)
