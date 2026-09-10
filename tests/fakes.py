from cados.services.trainer import TrainerSnapshot
from cados.services.hr_monitor import HRSnapshot


class FakeTrainer:
    mode_label = "Test Trainer"

    def __init__(self):
        self.telemetry = TrainerSnapshot(current_watts=200, cadence=90, connected=True, cadence_available=True, power_available=True)
        self.commands = []
        self.bluetooth = self
        self.available = True

    @property
    def connected(self):
        return self.telemetry.connected

    def ready_for_workout(self):
        return self.connected

    def read_snapshot(self):
        return self.telemetry

    def start_session(self):
        self.commands.append(("start",))

    def pause_session(self):
        self.commands.append(("pause",))

    def stop_session(self):
        self.commands.append(("stop",))

    def update(self, watts, cadence, dt, active):
        self.commands.append(("update", watts, active))
        return self.telemetry

    def status_text(self):
        return "Test Trainer verbunden"

    def close(self):
        self.commands.append(("close",))


class FakeHRMonitor:
    connected = True
    available = True

    def __init__(self):
        self.telemetry = HRSnapshot(heart_rate=140, connected=True, device_name="Test HR")

    def read_snapshot(self):
        return self.telemetry

    def close(self):
        pass
