"""Local CADOS Connector: Bluetooth and ERG control for the browser app.

The connector owns the trainer locally.  A temporary network outage therefore
never interrupts a started workout; live messages simply resume on reconnect.
"""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from queue import SimpleQueue
from math import ceil
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from cados import __version__
from cados.config import AppConfig
from cados.core.workout_engine import WorkoutEngine
from cados.services.hr_monitor import HRMonitorService
from cados.services.storage import DataStore
from cados.services.trainer import TrainerController
from cados.services.workout_catalog import WorkoutCatalog

logger = logging.getLogger(__name__)


class ConnectorService:
    PUBLISH_INTERVAL_SEC = 0.5
    BROWSER_IDLE_TIMEOUT_SEC = 10 * 60

    def __init__(self, config: AppConfig | None = None, *, status_callback: Callable[[dict], None] | None = None):
        self.config = config or AppConfig.load()
        self.store = DataStore(self.config.paths.database_path)
        self.catalog = WorkoutCatalog(self.config.paths.bundled_workouts_dir, self.store)
        self.trainer = TrainerController(self.config.trainer_scan_timeout_sec)
        self.hr_monitor = HRMonitorService(self.config.trainer_scan_timeout_sec)
        self.engine = WorkoutEngine(self.trainer, self.hr_monitor)
        self._stopping = False
        self._last_tick = time.monotonic()
        self._sync_needed = True
        self._next_sync_attempt = 0.0
        self._network_connected = False
        self._local_commands = SimpleQueue()
        self._last_session_id = None
        self._plan_id = None
        self._save_generation = 0
        self._status_callback = status_callback
        self._browser_presence_known = False
        self._browser_connected = False
        self._browser_absent_since: float | None = None

    def _report_status(self, **values: object) -> None:
        if self._status_callback is None:
            return
        try:
            self._status_callback(dict(values))
        except Exception:
            logger.debug("Connector-Status konnte nicht weitergegeben werden.", exc_info=True)

    def _set_browser_connected(self, connected: bool) -> None:
        self._browser_presence_known = True
        self._browser_connected = connected
        if connected:
            self._browser_absent_since = None
        elif self._browser_absent_since is None:
            self._browser_absent_since = time.monotonic()

    def _browser_idle_status(self, now: float) -> dict[str, object]:
        if not self._browser_presence_known or self._browser_connected:
            return {"browser_connected": self._browser_connected}
        active = self.engine.snapshot().state in {"running", "paused", "waiting_for_pedal"}
        if active:
            return {"browser_connected": False, "auto_close_deferred": True}
        elapsed = now - (self._browser_absent_since or now)
        return {
            "browser_connected": False,
            "auto_close_remaining_sec": max(0, ceil(self.BROWSER_IDLE_TIMEOUT_SEC - elapsed)),
        }

    def _should_auto_close(self, now: float) -> bool:
        if not self._browser_presence_known or self._browser_connected or self._browser_absent_since is None:
            return False
        if self.engine.snapshot().state in {"running", "paused", "waiting_for_pedal"}:
            return False
        return now - self._browser_absent_since >= self.BROWSER_IDLE_TIMEOUT_SEC

    @property
    def configured(self) -> bool:
        return bool(self.config.workout_library_url and self.config.workout_library_token)

    @property
    def websocket_url(self) -> str:
        parsed = urlsplit(self.config.workout_library_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunsplit((scheme, parsed.netloc, "/api/v1/live/connector", "", ""))

    def _connect_devices(self) -> None:
        if not self.trainer.ready_for_workout():
            trainer = self.trainer.pick_preferred_device(self.trainer.scan_devices())
            if trainer is not None:
                self.trainer.connect_device(trainer.identifier, trainer.name)
        if not self.hr_monitor.connected:
            devices = self.hr_monitor.scan_devices()
            if devices:
                device = devices[0]
                self.hr_monitor.connect(device.identifier, device.name)

    def _active_profile(self):
        profiles = self.store.list_profiles()
        return max(profiles, key=lambda profile: profile.updated_at) if profiles else None

    async def _handle_command(self, command: dict, send) -> None:
        name = command.get("name")
        try:
            if name == "connect":
                await asyncio.to_thread(self._connect_devices)
            elif name == "snapshot":
                await send(self._recovery())
            elif name == "start":
                if not self.trainer.ready_for_workout():
                    raise RuntimeError("Der Trainer ist noch nicht verbunden. Bitte zuerst verbinden.")
                payload = command.get("workout")
                if not isinstance(payload, dict):
                    raise ValueError("Das Workout fehlt.")
                source_name = Path(str(payload.get("source_name") or "browser-workout.json")).name
                workout = self.catalog.load_payload(payload, Path("browser") / source_name)
                from cados.models.profile import UserProfile
                profile = UserProfile.from_dict(command["profile"]) if command.get("profile") else self._active_profile()
                self.engine.set_profile(profile)
                self.engine.load_workout(workout, ftp_watts=(profile.ftp_watts if profile else None))
                self.engine.set_adaptive_erg(bool(command.get("adaptive_erg")))
                self._plan_id = command.get("plan_id")
                self._last_session_id = None
                self.engine.start()
                await send(self._recovery())
            elif name == "pause":
                self.engine.pause()
            elif name == "resume":
                self.engine.resume()
            elif name == "stop":
                self.engine.stop()
                self._save_pending_session()
            elif name == "erg_mode":
                self.engine.set_adaptive_erg(bool(command.get("adaptive_erg")))
            else:
                raise ValueError("Unbekannter Connector-Befehl")
        except Exception as exc:
            logger.warning("Connector-Befehl fehlgeschlagen: %s", exc)
            self._report_status(error=str(exc))
            await send({"type": "error", "message": str(exc)})

    def _save_pending_session(self) -> None:
        session = self.engine.pending_session
        if session is None:
            return
        session.plan_id = self._plan_id
        self.store.save_session(session)
        self._last_session_id = session.id
        self._save_generation += 1
        self.engine.acknowledge_session(session.id)
        self._sync_needed = True

    def _sync_completed_data(self) -> None:
        if not self._sync_needed:
            return
        from cados.services.account_sync import AccountSync
        from cados.services.workout_library import WorkoutLibraryClient

        client = WorkoutLibraryClient(self.config.workout_library_url, self.config.workout_library_token)
        AccountSync(self.store, client, self.config).run()

    def _telemetry(self) -> dict:
        snapshot = self.engine.snapshot()
        trainer = self.trainer.read_snapshot()
        hr = self.hr_monitor.read_snapshot()
        return {
            "type": "telemetry",
            "payload": {
                "state": snapshot.state,
                "ftp_test": self.engine.is_ftp_test,
                "started_at": self.engine.started_at,
                "auto_paused": snapshot.auto_paused,
                "session_id": self._last_session_id,
                "sync_pending": self._sync_needed,
                "ftp_watts": self.engine.workout.ftp_watts if self.engine.workout else None,
                "workout_name": snapshot.workout_name,
                "elapsed_sec": snapshot.elapsed_sec,
                "remaining_sec": snapshot.remaining_sec,
                "current_block_name": snapshot.current_block_name,
                "current_watts": snapshot.current_watts,
                "target_watts": snapshot.target_watts,
                "trainer_target_watts": snapshot.trainer_target_watts,
                "current_cadence": snapshot.current_cadence,
                "target_cadence": snapshot.target_cadence,
                "heart_rate": snapshot.heart_rate,
                "adaptive_erg": snapshot.adaptive_erg,
                "adaptive_relief_watts": snapshot.adaptive_relief_watts,
                "trainer_connected": trainer.connected,
                "trainer_name": trainer.device_name,
                "hr_connected": hr.connected,
                "hr_name": hr.device_name,
            },
        }

    def submit_local_command(self, name: str) -> None:
        if name in {"pause", "resume", "stop"}:
            self._local_commands.put({"name": name})

    def _recovery(self) -> dict:
        samples = self.engine.metrics.samples
        step = max(1, ceil(len(samples) / 1800))
        shown = samples[::step]
        if samples and (not shown or shown[-1] is not samples[-1]):
            shown = [*shown, samples[-1]]
        return {"type": "recovery", "payload": {
            "workout": self.engine.workout_template.to_dict() if self.engine.workout_template else None,
            "telemetry": self._telemetry()["payload"],
            "history": [{"elapsed": item["workout_elapsed_sec"] + item["duration_sec"],
                         "watts": item["watts"], "cadence": item["cadence"]} for item in shown],
        }}

    async def _local_loop(self) -> None:
        # Control, timekeeping and saving never wait for the network or device scans.
        self._last_tick = time.monotonic()
        while not self._stopping:
            now = time.monotonic()
            self.engine.tick(now - self._last_tick)  # Preserve suspend gaps for the engine's auto-pause.
            self._last_tick = now
            async def report(message):
                self._report_status(error=message.get("message", ""))
            while not self._local_commands.empty():
                await self._handle_command(self._local_commands.get_nowait(), report)
            self._save_pending_session()
            self._report_status(
                connected=self._network_connected,
                message="Mit CADOS verbunden" if self._network_connected else "Server nicht erreichbar. Training und Bedienung bleiben lokal aktiv.",
                **self._browser_idle_status(now), **self._telemetry()["payload"],
            )
            if self._should_auto_close(now):
                self._report_status(auto_close=True, message="Webseite seit 10 Minuten getrennt. Connector wird beendet.")
                self._stopping = True
            await asyncio.sleep(0.2)

    async def _sync_loop(self) -> None:
        while not self._stopping:
            if self._sync_needed and time.monotonic() >= self._next_sync_attempt:
                generation = self._save_generation
                try:
                    await asyncio.to_thread(self._sync_completed_data)
                    self._sync_needed = generation != self._save_generation
                except Exception as exc:
                    logger.info("Lokal gespeichert; Synchronisierung wird wiederholt: %s", exc)
                    self._next_sync_attempt = time.monotonic() + 30
            await asyncio.sleep(1)

    async def _network_loop(self) -> None:
        import websockets
        import certifi
        tls_context = ssl.create_default_context(cafile=certifi.where())
        while not self._stopping:
            try:
                async with websockets.connect(
                    self.websocket_url,
                    additional_headers={"Authorization": "Bearer " + self.config.workout_library_token},
                    ping_interval=20, ping_timeout=20, open_timeout=10,
                    ssl=tls_context if self.websocket_url.startswith("wss://") else None,
                ) as socket:
                    self._network_connected = True
                    async def send(message):
                        await socket.send(json.dumps(message, separators=(",", ":")))
                    await send({"type": "status", "message": "CADOS Connector bereit", "version": __version__})
                    await send(self._recovery())
                    async def publish():
                        while not self._stopping:
                            await send(self._telemetry())
                            await asyncio.sleep(self.PUBLISH_INTERVAL_SEC)
                    publisher = asyncio.create_task(publish())
                    try:
                        async for raw in socket:
                            message = json.loads(raw)
                            if not isinstance(message, dict):
                                continue
                            if message.get("type") == "browser":
                                self._set_browser_connected(bool(message.get("connected")))
                                if message.get("connected"):
                                    await send(self._recovery())
                            else:
                                await self._handle_command(message, send)
                    finally:
                        publisher.cancel()
                        await asyncio.gather(publisher, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Serververbindung getrennt; lokale Steuerung läuft weiter: %s", exc)
            finally:
                self._network_connected = False
                self._set_browser_connected(False)
            await asyncio.sleep(3)

    async def run(self) -> None:
        if not self.configured:
            raise RuntimeError("Bitte zuerst einmal in der CADOS-Desktop-App anmelden.")
        tasks = [asyncio.create_task(loop()) for loop in (self._local_loop, self._network_loop, self._sync_loop)]
        try:
            # Local-loop completion or failure must also shut down the network tasks.
            await tasks[0]
        finally:
            self._stopping = True
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.engine.stop()
            self._save_pending_session()
            self.trainer.close()
            self.hr_monitor.close()

    def close(self) -> None:
        # Called by Qt's thread; engine and Bluetooth cleanup belong to the worker.
        self._stopping = True


def run() -> int:
    from cados.logging_utils import configure_logging

    config = AppConfig.load()
    configure_logging(config.paths.logs_dir)
    service = ConnectorService(config)
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        pass
    finally:
        service.close()
    return 0
