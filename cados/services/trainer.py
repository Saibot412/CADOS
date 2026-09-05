from __future__ import annotations

import asyncio
import logging
import struct
import threading
from dataclasses import dataclass
from typing import Any

from cados.services.async_loop import AsyncLoopThread
from cados.services.trainer_control import TrainerCommandWorker

logger = logging.getLogger(__name__)

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # pragma: no cover - optional dependency at runtime
    BleakClient = None
    BleakScanner = None


@dataclass(slots=True)
class TrainerDevice:
    identifier: str
    name: str


@dataclass(slots=True)
class TrainerSnapshot:
    current_watts: int = 0
    cadence: int = 0
    connected: bool = False
    source_label: str = "Bluetooth FTMS"
    device_name: str = "Nicht verbunden"
    status_text: str = "Bluetooth nicht verbunden"


class FtmsBluetoothService:
    FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
    INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"
    CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"
    STATUS_UUID = "00002ada-0000-1000-8000-00805f9b34fb"
    PREFERRED_NAME_TOKENS = ("wahoo", "kickr")

    RESPONSE_CODE = 0x80
    REQUEST_CONTROL = 0x00
    SET_TARGET_POWER = 0x05
    START_OR_RESUME = 0x07
    STOP_OR_PAUSE = 0x08
    STOP = 0x01
    PAUSE = 0x02

    def __init__(self, scan_timeout_sec: int = 5):
        self._scan_timeout_sec = scan_timeout_sec
        self._loop_thread = AsyncLoopThread() if BleakClient and BleakScanner else None
        self._client: Any | None = None
        self._lock = threading.Lock()
        self._pending_control_response: asyncio.Future[tuple[int, int]] | None = None
        self._pending_opcode: int | None = None
        self._control_granted = False
        self._ready_for_control = False
        self._closing = False
        self._command_lock = asyncio.Lock()
        self._snapshot = TrainerSnapshot(
            connected=False,
            source_label="Bluetooth FTMS",
            device_name="Nicht verbunden",
            status_text="Bluetooth nicht verbunden",
        )
        self._last_response = "Keine Steuerantwort"

    @property
    def available(self) -> bool:
        return self._loop_thread is not None

    @property
    def connected(self) -> bool:
        return bool(self._ready_for_control and self._client and self._client.is_connected)

    def scan_devices(self) -> list[TrainerDevice]:
        if not self.available:
            return []
        return self._loop_thread.call(self._scan_devices())

    async def _scan_devices(self) -> list[TrainerDevice]:
        assert BleakScanner is not None
        found = await BleakScanner.discover(timeout=self._scan_timeout_sec, return_adv=True)
        devices: list[TrainerDevice] = []
        for device, advertisement in found.values():
            name = device.name or device.address or "Bluetooth-Gerät"
            uuids = {uuid.lower() for uuid in advertisement.service_uuids}
            looks_like_trainer = any(token in name.lower() for token in (*self.PREFERRED_NAME_TOKENS, "trainer"))
            if self.FTMS_SERVICE_UUID in uuids or looks_like_trainer:
                devices.append(TrainerDevice(identifier=device.address, name=name))
        devices.sort(key=self._device_sort_key)
        return devices

    @classmethod
    def _device_sort_key(cls, device: TrainerDevice) -> tuple[int, str]:
        return (0 if cls.is_preferred_device_name(device.name) else 1, device.name.lower())

    @classmethod
    def is_preferred_device_name(cls, name: str) -> bool:
        lowered = name.lower()
        return any(token in lowered for token in cls.PREFERRED_NAME_TOKENS)

    def connect(self, identifier: str, fallback_name: str | None = None) -> None:
        if not self.available:
            raise RuntimeError("Bleak ist nicht installiert.")
        self._loop_thread.call(self._connect(identifier, fallback_name or identifier))

    async def _connect(self, identifier: str, fallback_name: str) -> None:
        assert BleakClient is not None
        if self._closing:
            raise RuntimeError("Trainer wird bereits beendet.")
        async with self._command_lock:
            await self._disconnect()
            client = BleakClient(identifier, disconnected_callback=self._handle_disconnect)
            self._client = client
            try:
                await client.connect()
                await client.start_notify(self.INDOOR_BIKE_DATA_UUID, self._handle_indoor_bike_data)
                await client.start_notify(self.CONTROL_POINT_UUID, self._handle_control_point_response)
                try:
                    await client.start_notify(self.STATUS_UUID, self._handle_status)
                except Exception:
                    logger.debug("Optionale FTMS-Statusmeldungen nicht verfügbar.")
                if not await self._ensure_control():
                    raise RuntimeError("Trainer hat die Steuerfreigabe nicht bestätigt.")
                self._ready_for_control = True
                self._set_snapshot(connected=True, source_label=fallback_name,
                                   device_name=fallback_name, status_text="Verbunden")
            except BaseException:
                await self._disconnect()
                raise

    def disconnect(self) -> None:
        if not self.available:
            return
        self._loop_thread.call(self._disconnect(), timeout=10.0)

    async def _disconnect(self) -> None:
        self._ready_for_control = False
        if self._client is None:
            return
        client, self._client = self._client, None
        try:
            if client.is_connected:
                await client.disconnect()
        finally:
            self._control_granted = False
            self._set_snapshot(
                current_watts=0,
                cadence=0,
                connected=False,
                source_label="Trainer",
                device_name="Nicht verbunden",
                status_text="Bluetooth nicht verbunden",
            )

    def start_session(self) -> bool:
        if self.available and self.connected:
            return self._loop_thread.call(self._run_control_command(bytes([self.START_OR_RESUME]))) == 0x01
        return False

    def pause_session(self) -> bool:
        if self.available and self.connected:
            return self._loop_thread.call(self._run_control_command(bytes([self.STOP_OR_PAUSE, self.PAUSE]))) == 0x01
        return False

    def stop_session(self) -> bool:
        if self.available and self.connected:
            return self._loop_thread.call(self._run_control_command(bytes([self.STOP_OR_PAUSE, self.STOP]))) == 0x01
        return False

    def set_target_power(self, watts: int) -> bool:
        if self.available and self.connected:
            payload = bytes([self.SET_TARGET_POWER]) + struct.pack("<h", int(watts))
            return self._loop_thread.call(self._run_control_command(payload)) == 0x01
        return False

    async def _ensure_control(self) -> bool:
        if self._control_granted:
            return True
        result = await self._write_control(bytes([self.REQUEST_CONTROL]))
        self._control_granted = result == 0x01
        return self._control_granted

    async def _run_control_command(self, payload: bytes) -> int | None:
        async with self._command_lock:
            return await self._run_locked_command(payload)

    async def _run_locked_command(self, payload: bytes) -> int | None:
        opcode = payload[0] if payload else None
        if opcode is None:
            return None

        if opcode != self.REQUEST_CONTROL and not await self._ensure_control():
            return None

        result = await self._write_control(payload)
        if result == 0x05 and opcode != self.REQUEST_CONTROL:
            self._control_granted = False
            if await self._ensure_control():
                result = await self._write_control(payload)
        return result

    async def _write_control(self, payload: bytes) -> int | None:
        if self._client is None or not self._client.is_connected:
            return None
        opcode = payload[0] if payload else None
        if opcode is None:
            return None
        pending_response = asyncio.get_running_loop().create_future()
        self._pending_control_response = pending_response
        self._pending_opcode = opcode
        try:
            await self._client.write_gatt_char(self.CONTROL_POINT_UUID, payload, response=True)
            logger.info("FTMS Control write 0x%02X (%s)", opcode, payload.hex(" "))
            request_opcode, result_code = await asyncio.wait_for(pending_response, timeout=5.0)
            if request_opcode != opcode:
                logger.warning(
                    "FTMS Control Antwort passt nicht zum Request: erwartet 0x%02X, erhalten 0x%02X",
                    opcode,
                    request_opcode,
                )
            if opcode == self.REQUEST_CONTROL:
                self._control_granted = result_code == 0x01
            elif result_code == 0x05:
                self._control_granted = False
            return result_code
        except asyncio.TimeoutError:
            self._control_granted = False
            self._last_response = f"Op 0x{opcode:02X}: keine Antwort"
            logger.warning("FTMS Control keine Antwort fuer 0x%02X", opcode)
            self._set_snapshot(status_text=self._last_response)
            return None
        except Exception as exc:
            logger.warning("Control-Point-Schreibvorgang fehlgeschlagen: %s", exc)
            self._set_snapshot(status_text=f"Bluetooth-Fehler: {exc}")
            return None
        finally:
            if self._pending_control_response is pending_response:
                self._pending_control_response = None
                self._pending_opcode = None

    def read_snapshot(self) -> TrainerSnapshot:
        with self._lock:
            return TrainerSnapshot(
                current_watts=self._snapshot.current_watts,
                cadence=self._snapshot.cadence,
                connected=self._snapshot.connected,
                source_label=self._snapshot.source_label,
                device_name=self._snapshot.device_name,
                status_text=self._snapshot.status_text,
            )

    def close(self) -> None:
        self._closing = True
        if not self.available:
            return
        try:
            self.disconnect()
        except Exception:
            logger.exception("Bluetooth-Trainer konnte beim Beenden nicht sauber getrennt werden.")
        finally:
            self._loop_thread.stop()

    def _set_snapshot(self, **changes: Any) -> None:
        with self._lock:
            current = {
                "current_watts": self._snapshot.current_watts,
                "cadence": self._snapshot.cadence,
                "connected": self._snapshot.connected,
                "source_label": self._snapshot.source_label,
                "device_name": self._snapshot.device_name,
                "status_text": self._snapshot.status_text,
            }
            current.update(changes)
            self._snapshot = TrainerSnapshot(**current)

    def _handle_disconnect(self, _: Any) -> None:
        self._ready_for_control = False
        self._control_granted = False
        self._set_snapshot(
            current_watts=0,
            cadence=0,
            connected=False,
            source_label="Trainer",
            device_name="Nicht verbunden",
            status_text="Verbindung getrennt",
        )

    def _handle_status(self, _: Any, data: bytearray) -> None:
        if not data:
            return
        status_code = data[0]
        labels = {
            0x02: "Trainer gestoppt oder pausiert",
            0x04: "Trainer gestartet oder fortgesetzt",
            0x08: "Zielleistung geaendert",
        }
        self._set_snapshot(status_text=labels.get(status_code, f"Status 0x{status_code:02X}"))

    def _handle_control_point_response(self, _: Any, data: bytearray) -> None:
        if len(data) < 3 or data[0] != self.RESPONSE_CODE:
            return
        request_opcode = data[1]
        result_code = data[2]
        result_map = {
            0x01: "Erfolg",
            0x02: "Op Code nicht unterstuetzt",
            0x03: "Ungueltiger Parameter",
            0x04: "Operation fehlgeschlagen",
            0x05: "Control nicht erlaubt",
        }
        self._last_response = f"Op 0x{request_opcode:02X}: {result_map.get(result_code, f'Code 0x{result_code:02X}')}"
        logger.info("FTMS Control response 0x%02X -> 0x%02X", request_opcode, result_code)
        if (self._pending_control_response is not None
                and not self._pending_control_response.done()
                and request_opcode == self._pending_opcode):
            self._pending_control_response.set_result((request_opcode, result_code))
        self._set_snapshot(status_text=self._last_response)

    def _handle_indoor_bike_data(self, _: Any, data: bytearray) -> None:
        try:
            current_watts, cadence = self._parse_indoor_bike_data(bytes(data))
        except Exception as exc:
            logger.debug("Indoor-Bike-Daten konnten nicht geparst werden: %s", exc)
            return
        self._set_snapshot(
            current_watts=current_watts,
            cadence=cadence,
            connected=self._ready_for_control,
            source_label="Bluetooth FTMS",
            status_text=self._last_response if self._last_response != "Keine Steuerantwort" else "Verbunden",
        )

    @staticmethod
    def _parse_indoor_bike_data(payload: bytes) -> tuple[int, int]:
        if len(payload) < 2:
            return 0, 0

        flags = int.from_bytes(payload[:2], "little")
        offset = 2

        if not flags & (1 << 0):
            offset += 2
        if flags & (1 << 1):
            offset += 2

        cadence = 0
        if flags & (1 << 2):
            cadence_raw = struct.unpack_from("<H", payload, offset)[0]
            cadence = round(cadence_raw / 2)
            offset += 2
        if flags & (1 << 3):
            offset += 2
        if flags & (1 << 4):
            offset += 3
        if flags & (1 << 5):
            offset += 2

        current_watts = 0
        if flags & (1 << 6):
            current_watts = struct.unpack_from("<h", payload, offset)[0]
            offset += 2

        return current_watts, cadence


class TrainerController:
    def __init__(self, scan_timeout_sec: int = 5, *, bluetooth: FtmsBluetoothService | None = None, retry_sec: float = 1.0):
        self.bluetooth = bluetooth if bluetooth is not None else FtmsBluetoothService(scan_timeout_sec)
        self._commands = TrainerCommandWorker(self.bluetooth, retry_sec=retry_sec)
        self._commands.connection_changed(self.bluetooth.connected)

    @property
    def mode_label(self) -> str:
        return "Bluetooth FTMS"

    def ready_for_workout(self) -> bool:
        return self.bluetooth.connected

    def scan_devices(self) -> list[TrainerDevice]:
        return self.bluetooth.scan_devices()

    @staticmethod
    def pick_preferred_device(devices: list[TrainerDevice]) -> TrainerDevice | None:
        if not devices:
            return None
        for device in devices:
            if FtmsBluetoothService.is_preferred_device_name(device.name):
                return device
        return devices[0]

    def connect_device(self, identifier: str, device_name: str | None = None) -> None:
        self._commands.connection_changed(False)
        self.bluetooth.connect(identifier, device_name)
        self._commands.connection_changed(self.bluetooth.connected)

    def disconnect_device(self) -> None:
        self.bluetooth.disconnect()
        self._commands.connection_changed(False)

    def start_session(self) -> None:
        self._commands.set_mode("running")

    def pause_session(self) -> None:
        self._commands.set_mode("paused")

    def stop_session(self) -> None:
        self._commands.set_mode("stopped")

    def read_snapshot(self) -> TrainerSnapshot:
        return self.bluetooth.read_snapshot()

    def update(self, target_watts: int, target_cadence: int | None, dt: float, active: bool) -> TrainerSnapshot:
        del target_cadence, dt
        self._commands.connection_changed(self.bluetooth.connected)
        self._commands.set_power(max(0, min(32767, target_watts)) if active else None)
        return self.read_snapshot()

    def status_text(self) -> str:
        snapshot = self.bluetooth.read_snapshot()
        if snapshot.connected:
            return f"{snapshot.device_name} | {snapshot.status_text}"
        if not self.bluetooth.available:
            return "Bluetooth nicht installiert"
        return f"Trainer | {snapshot.status_text}"

    def close(self) -> None:
        self._commands.close()
        self.bluetooth.close()
