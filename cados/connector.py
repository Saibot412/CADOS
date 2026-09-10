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
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from cados import __version__
from cados.connector_local import LocalTransport
from cados.config import AppConfig
from cados.core.workout_engine import WorkoutEngine
from cados.services.hr_monitor import HRMonitorService
from cados.services.storage import DataStore
from cados.services.training_journal import TrainingJournal
from cados.services.trainer import TrainerController
from cados.services.workout_catalog import WorkoutCatalog

logger = logging.getLogger(__name__)


class ConnectorService:
    PUBLISH_INTERVAL_SEC = 0.5
    BROWSER_IDLE_TIMEOUT_SEC = 10 * 60

    def __init__(self, config: AppConfig | None = None, *, status_callback: Callable[[dict], None] | None = None):
        self.config = config or AppConfig.load()
        account = self.config.current_account
        database_path = self.config.database_path_for_account(account) if account else self.config.paths.database_path
        self.store = DataStore(database_path)
        self.catalog = WorkoutCatalog(self.config.paths.bundled_workouts_dir, self.store)
        self.trainer = TrainerController(self.config.trainer_scan_timeout_sec)
        self.hr_monitor = HRMonitorService(self.config.trainer_scan_timeout_sec)
        self.engine = WorkoutEngine(self.trainer, self.hr_monitor)
        self.journal = TrainingJournal(self.store)
        self._restore_candidate = self.journal.load()
        self._devices_lock = asyncio.Lock()
        self._device_choices = {'trainer': [], 'hr': []}
        self._device_status = ''
        self._updating = False
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
        self.local = LocalTransport(self)
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
        if not self._browser_presence_known or self._browser_connected or self.local.clients:
            return {"browser_connected": self._browser_connected or bool(self.local.clients)}
        active = self.engine.snapshot().state in {"running", "paused", "waiting_for_pedal"}
        if active:
            return {"browser_connected": False, "auto_close_deferred": True}
        elapsed = now - (self._browser_absent_since or now)
        return {
            "browser_connected": False,
            "auto_close_remaining_sec": max(0, ceil(self.BROWSER_IDLE_TIMEOUT_SEC - elapsed)),
        }

    def _should_auto_close(self, now: float) -> bool:
        if not self._browser_presence_known or self._browser_connected or self.local.clients or self._browser_absent_since is None:
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

    def _scan_devices(self) -> dict:
        self._device_choices = {'trainer': self.trainer.scan_devices(), 'hr': self.hr_monitor.scan_devices()}
        return self._devices_message()

    def _devices_message(self):
        return {'type': 'devices', 'payload': {kind: [asdict(device) for device in choices]
                for kind, choices in self._device_choices.items()},
                'preferences': getattr(self.config, 'device_preferences', {})}

    def _remember_device(self, kind, identifier, name):
        preferences = getattr(self.config, 'device_preferences', {})
        preferences.update({kind: identifier, kind + '_name': name})
        self.config.device_preferences = preferences
        self.config.save_settings({'device_preferences': preferences})

    def _select_device(self, kind, identifier):
        if kind not in {'trainer', 'hr'}:
            raise ValueError('Ungültiger Gerätetyp.')
        device = next((d for d in self._device_choices[kind] if d.identifier == identifier), None)
        if device is None:
            raise ValueError('Bitte zuerst erneut nach Geräten suchen.')
        if kind == 'trainer':
            self.trainer.connect_device(device.identifier, device.name)
        else:
            self.hr_monitor.connect(device.identifier, device.name)
        self._remember_device(kind, device.identifier, device.name)

    def _connect_devices(self) -> None:
        preferences = getattr(self.config, 'device_preferences', {})
        if not self.trainer.ready_for_workout():
            if preferences.get('trainer'):
                self.trainer.connect_device(preferences['trainer'], preferences.get('trainer_name'))
            else:
                raise RuntimeError('Bitte Trainer unter Geräte auswählen.')
        if not self.hr_monitor.connected and preferences.get('hr'):
            self.hr_monitor.connect(preferences['hr'], preferences.get('hr_name'))

    async def _reconnect_devices(self) -> None:
        while not self._stopping:
            preferences = getattr(self.config, 'device_preferences', {})
            for kind in ('trainer', 'hr'):
                if self._stopping:
                    break
                connected = self.trainer.ready_for_workout() if kind == 'trainer' else self.hr_monitor.connected
                if not preferences.get(kind) or connected or self._devices_lock.locked():
                    continue
                async with self._devices_lock:
                    try:
                        if kind == 'trainer':
                            await asyncio.to_thread(self.trainer.connect_device, preferences[kind], preferences.get(kind + '_name'))
                        else:
                            await asyncio.to_thread(self.hr_monitor.connect, preferences[kind], preferences.get(kind + '_name'))
                        self._device_status = ''
                    except Exception as exc:
                        self._device_status = str(exc)
            await asyncio.sleep(10)

    def _active_profile(self):
        profiles = self.store.list_profiles()
        return max(profiles, key=lambda profile: profile.updated_at) if profiles else None

    async def _handle_command(self, command: dict, send) -> None:
        name = command.get("name")
        try:
            if name in {"start", "restore"} and self._updating:
                raise RuntimeError("Connector-Update läuft. Bitte kurz warten.")
            if name == "update":
                import sys
                if self.engine.state in {"running", "paused", "waiting_for_pedal"} or self._restore_candidate:
                    raise RuntimeError("Bitte vor dem Update das Training beenden oder die unterbrochene Einheit speichern.")
                if not getattr(sys, 'frozen', False):
                    raise RuntimeError("Updates werden aus der installierten Connector-App gestartet.")
                if self._updating:
                    return
                self._updating = True
                from cados.connector_update import download_update
                try:
                    self._report_status(update_message="Update wird heruntergeladen und geprüft …")
                    update = await asyncio.to_thread(download_update, self.config.workout_library_url,
                                                     self.config.paths.data_dir / 'updates')
                    self._report_status(update_ready=update)
                except Exception:
                    self._updating = False
                    raise
            elif name == "scan_devices":
                if self._devices_lock.locked():
                    raise RuntimeError('Gerätesuche oder Verbindung läuft bereits. Bitte kurz warten.')
                async with self._devices_lock:
                    await send(await asyncio.to_thread(self._scan_devices))
            elif name in {"select_device", "disconnect_device"}:
                kind = command.get('kind')
                if kind not in {'trainer', 'hr'}:
                    raise ValueError('Ungültiger Gerätetyp.')
                if kind == 'trainer' and self.engine.state in {'running', 'paused', 'waiting_for_pedal'}:
                    raise RuntimeError('Bitte das Training beenden, bevor du einen anderen Trainer auswählst.')
                async with self._devices_lock:
                    if kind == 'trainer' and self.engine.state in {'running', 'paused', 'waiting_for_pedal'}:
                        raise RuntimeError('Bitte das Training vor einem Trainerwechsel beenden.')
                    if name == 'select_device':
                        await asyncio.to_thread(self._select_device, kind, command.get('identifier'))
                    else:
                        self._remember_device(kind, '', '')
                        action = self.trainer.disconnect_device if kind == 'trainer' else self.hr_monitor.disconnect
                        await asyncio.to_thread(action)
                    self._device_status = ''
                    await send(self._devices_message())
            elif name == "connect":
                async with self._devices_lock:
                    await asyncio.to_thread(self._connect_devices)
            elif name == "snapshot":
                await send(self._recovery())
            elif name in {"restore", "save_recovered"}:
                if self._restore_candidate is None:
                    raise ValueError("Keine unterbrochene Einheit vorhanden.")
                draft = self._restore_candidate
                workout = self.catalog.load_payload(draft['workout'], Path('recovered.json'))
                self.engine.restore_checkpoint(draft, workout)
                self._plan_id = draft.get('plan_id')
                self._restore_candidate = None
                if name == 'save_recovered':
                    self.engine.stop()
                    self._save_pending_session()
                await send(self._recovery())
            elif name == "start":
                if self._devices_lock.locked():
                    raise RuntimeError("Bitte warten, bis die Gerätesuche oder Verbindung abgeschlossen ist.")
                if self._restore_candidate:
                    raise RuntimeError("Bitte zuerst die unterbrochene Einheit wiederherstellen oder speichern.")
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
            if name in {"scan_devices", "select_device", "disconnect_device", "connect"}:
                self._device_status = str(exc)
            logger.warning("Connector-Befehl fehlgeschlagen: %s", exc)
            self._report_status(error=str(exc))
            await send({"type": "error", "message": str(exc)})

    def _save_pending_session(self) -> None:
        session = self.engine.pending_session
        if session is None:
            return
        session.plan_id = self._plan_id
        self.store.save_session(session)
        self.journal.clear()
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
                "recovery_available": ({"name": self._restore_candidate['workout']['name'],
                    "elapsed_sec": self._restore_candidate['elapsed_sec']} if self._restore_candidate else None),
                "updating": self._updating,
                "server_connected": self._network_connected,
                "account_email": (self.config.current_account or {}).get('email', ''),
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
                "measured_cadence": trainer.cadence,
                "cadence_available": getattr(trainer, 'cadence_available', False),
                "power_available": getattr(trainer, 'power_available', False),
                "trainer_min_power": getattr(trainer, 'min_power', None),
                "trainer_max_power": getattr(trainer, 'max_power', None),
                "device_status": self._device_status,
                "devices_busy": self._devices_lock.locked(),
                "hr_data_available": getattr(hr, 'data_available', False),
                "trainer_name": trainer.device_name,
                "hr_connected": hr.connected,
                "hr_name": hr.device_name,
            },
        }

    def submit_local_command(self, name: str) -> None:
        if name in {"pause", "resume", "stop", "restore", "save_recovered", "update"}:
            self._local_commands.put({"name": name})

    def _recovery(self) -> dict:
        samples = self.engine.metrics.samples
        step = max(1, ceil(len(samples) / 1800))
        shown = samples[::step]
        if samples and (not shown or shown[-1] is not samples[-1]):
            shown = [*shown, samples[-1]]
        return {"type": "recovery", "local_access": self.local.access, "payload": {
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

    async def _checkpoint_loop(self) -> None:
        while not self._stopping:
            checkpoint = self.engine.checkpoint()
            if checkpoint:
                checkpoint['plan_id'] = self._plan_id
                samples = list(self.engine.metrics.samples)
                try:
                    await asyncio.to_thread(self.journal.save, checkpoint, samples)
                except Exception:
                    logger.exception("Trainingssicherung fehlgeschlagen")
                    self._report_status(error="Trainingssicherung fehlgeschlagen. Bitte freien Speicher prüfen.")
            await asyncio.sleep(5)

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
                    await send({"type": "status", "message": "CADOS Connector bereit", "version": __version__, "local_access": self.local.access})
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
            raise RuntimeError("Bitte den CADOS Connector mit Fenster starten und anmelden (python -m cados).")
        tasks = [asyncio.create_task(loop()) for loop in (self._local_loop, self._network_loop, self._sync_loop, self._checkpoint_loop, self.local.run, self._reconnect_devices)]
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
