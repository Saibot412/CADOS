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
from pathlib import Path
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

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig.load()
        self.store = DataStore(self.config.paths.database_path)
        self.catalog = WorkoutCatalog(self.config.paths.bundled_workouts_dir, self.store)
        self.trainer = TrainerController(self.config.trainer_scan_timeout_sec)
        self.hr_monitor = HRMonitorService(self.config.trainer_scan_timeout_sec)
        self.engine = WorkoutEngine(self.trainer, self.hr_monitor)
        self._stopping = False
        self._last_tick = time.monotonic()
        self._sync_needed = False
        self._next_sync_attempt = 0.0

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
            elif name == "start":
                if not self.trainer.ready_for_workout():
                    raise RuntimeError("Der Trainer ist noch nicht verbunden. Bitte zuerst verbinden.")
                payload = command.get("workout")
                if not isinstance(payload, dict):
                    raise ValueError("Das Workout fehlt.")
                source_name = Path(str(payload.get("source_name") or "browser-workout.json")).name
                workout = self.catalog.load_payload(payload, Path("browser") / source_name)
                self.engine.set_profile(self._active_profile())
                self.engine.set_adaptive_erg(bool(command.get("adaptive_erg")))
                self.engine.load_workout(workout, ftp_watts=(self._active_profile().ftp_watts if self._active_profile() else None))
                self.engine.start()
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
            await send({"type": "error", "message": str(exc)})

    def _save_pending_session(self) -> None:
        session = self.engine.pending_session
        if session is None:
            return
        self.store.save_session(session)
        self.engine.acknowledge_session(session.id)
        self._sync_needed = True

    def _sync_completed_data(self) -> None:
        if not self._sync_needed:
            return
        from cados.services.account_sync import AccountSync
        from cados.services.workout_library import WorkoutLibraryClient

        client = WorkoutLibraryClient(self.config.workout_library_url, self.config.workout_library_token)
        AccountSync(self.store, client, self.config).run()
        self._sync_needed = False

    def _telemetry(self) -> dict:
        snapshot = self.engine.snapshot()
        trainer = self.trainer.read_snapshot()
        hr = self.hr_monitor.read_snapshot()
        return {
            "type": "telemetry",
            "payload": {
                "state": snapshot.state,
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

    async def run(self) -> None:
        if not self.configured:
            raise RuntimeError("Bitte zuerst einmal in der CADOS-Desktop-App anmelden.")
        try:
            import websockets
            import certifi
        except ImportError as exc:  # pragma: no cover - handled by packaged dependency
            raise RuntimeError("Der CADOS Connector benötigt die Netzwerk-Abhängigkeiten.") from exc

        # The packaged app must not depend on the macOS system certificate store:
        # on some Macs it is unavailable to embedded Python.  certifi retains
        # regular certificate and hostname validation using Mozilla's CA roots.
        tls_context = ssl.create_default_context(cafile=certifi.where())

        async def send(socket, message: dict) -> None:
            await socket.send(json.dumps(message, separators=(",", ":")))

        while not self._stopping:
            try:
                async with websockets.connect(
                    self.websocket_url,
                    additional_headers={"Authorization": "Bearer " + self.config.workout_library_token},
                    ping_interval=20, ping_timeout=20,
                    ssl=tls_context if self.websocket_url.startswith("wss://") else None,
                ) as socket:
                    await send(socket, {
                        "type": "status", "message": "CADOS Connector bereit", "version": __version__,
                    })
                    receiver = asyncio.create_task(socket.recv())
                    last_publish = 0.0
                    self._last_tick = time.monotonic()
                    while not self._stopping:
                        now = time.monotonic()
                        self.engine.tick(min(1.0, now - self._last_tick))
                        self._last_tick = now
                        self._save_pending_session()
                        if self._sync_needed and now >= self._next_sync_attempt:
                            try:
                                await asyncio.to_thread(self._sync_completed_data)
                            except Exception as exc:
                                logger.info("Training wird bei der nächsten Verbindung synchronisiert: %s", exc)
                                self._next_sync_attempt = now + 30
                        if now - last_publish >= self.PUBLISH_INTERVAL_SEC:
                            await send(socket, self._telemetry())
                            last_publish = now
                        done, _ = await asyncio.wait({receiver}, timeout=0.2)
                        if receiver in done:
                            message = json.loads(receiver.result())
                            if isinstance(message, dict):
                                await self._handle_command(message, lambda item: send(socket, item))
                            receiver = asyncio.create_task(socket.recv())
                    receiver.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Connector ist vorübergehend nicht mit dem Server verbunden: %s", exc)
                await asyncio.sleep(3)
        self._save_pending_session()

    def close(self) -> None:
        self._stopping = True
        self._save_pending_session()
        self.trainer.close()
        self.hr_monitor.close()


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
