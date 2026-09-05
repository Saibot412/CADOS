from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

logger = logging.getLogger(__name__)


class TrainerCommands(Protocol):
    def start_session(self) -> bool: ...
    def pause_session(self) -> bool: ...
    def stop_session(self) -> bool: ...
    def set_target_power(self, watts: int) -> bool: ...


class TrainerCommandWorker:
    """Serialize BLE writes off the UI thread; retain only the latest intent.

    A value is confirmed only after an FTMS success response. Failed commands
    are retried, while newer pause/stop requests take priority over power.
    """

    def __init__(self, service: TrainerCommands, retry_sec: float = 1.0):
        self.service = service
        self.retry_sec = retry_sec
        self._condition = threading.Condition()
        self._connected = False
        self._generation = 0
        self._mode: str | None = None
        self._confirmed_mode: str | None = None
        self._power: int | None = None
        self._confirmed_power: int | None = None
        self._retry_at = 0.0
        self._closing = False
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="cados-trainer-control", daemon=True)
        self._thread.start()

    def connection_changed(self, connected: bool) -> None:
        with self._condition:
            if connected != self._connected:
                self._connected = connected
                self._generation += 1
                self._confirmed_mode = None
                self._confirmed_power = None
                self._retry_at = 0.0
                self._condition.notify_all()

    def set_mode(self, mode: str) -> None:
        with self._condition:
            if self._closing:
                return
            if mode != self._mode:
                self._mode = mode
                self._power = None
                self._retry_at = 0.0
                self._condition.notify_all()

    def set_power(self, watts: int | None) -> None:
        with self._condition:
            if self._closing:
                return
            if watts != self._power:
                self._power = watts
                self._condition.notify_all()

    def _next_command(self) -> tuple[str, str | int] | None:
        if not self._connected:
            return None
        if self._mode is not None and self._mode != self._confirmed_mode:
            return "mode", self._mode
        if self._mode == "running" and self._power is not None and self._power != self._confirmed_power:
            return "power", self._power
        return None

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._closed:
                    command = self._next_command()
                    if self._closing and command is None:
                        return
                    delay = self._retry_at - time.monotonic()
                    if command is not None and delay <= 0:
                        break
                    self._condition.wait(timeout=delay if command and delay > 0 else None)
                if self._closed:
                    return
                generation = self._generation
            kind, value = command
            try:
                if kind == "power":
                    success = self.service.set_target_power(int(value))
                else:
                    method = {"running": self.service.start_session,
                              "paused": self.service.pause_session,
                              "stopped": self.service.stop_session}[value]
                    success = method()
            except Exception:
                logger.exception("Trainer-Steuerbefehl fehlgeschlagen; erneuter Versuch folgt.")
                success = False
            with self._condition:
                if generation != self._generation:
                    continue
                if success:
                    if kind == "mode":
                        self._confirmed_mode = str(value)
                        self._confirmed_power = None
                    else:
                        self._confirmed_power = int(value)
                    self._retry_at = 0.0
                elif command == self._next_command():
                    self._retry_at = time.monotonic() + self.retry_sec
                self._condition.notify_all()

    def close(self, timeout: float = 16.0) -> None:
        """Best-effort stop on application exit, with a bounded wait."""
        with self._condition:
            if self._closed:
                return
            self._closing = True
            # Do not stop an unrelated trainer if this app never started it.
            if self._mode is not None:
                self._mode = "stopped"
            self._power = None
            self._retry_at = 0.0
            self._condition.notify_all()
        self._thread.join(timeout=timeout)
        with self._condition:
            self._closed = True
            self._condition.notify_all()
