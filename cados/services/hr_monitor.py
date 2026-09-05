from __future__ import annotations

import logging
import struct
import threading
from dataclasses import dataclass
from typing import Any

from cados.services.async_loop import AsyncLoopThread

logger = logging.getLogger(__name__)

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # pragma: no cover - optional dependency at runtime
    BleakClient = None
    BleakScanner = None


HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

GARMIN_NAME_TOKENS = ("garmin", "forerunner", "fenix", "venu", "vivoactive", "enduro", "instinct", "epix")
HR_NAME_TOKENS = (*GARMIN_NAME_TOKENS, "polar", "wahoo tickr", "coospo", "magene", "heart", "hr")


@dataclass(slots=True)
class HRDevice:
    identifier: str
    name: str


@dataclass(slots=True)
class HRSnapshot:
    heart_rate: int = 0
    connected: bool = False
    device_name: str = "Nicht verbunden"
    status_text: str = "HR-Monitor nicht verbunden"


class HRMonitorService:
    """Connects to a BLE Heart Rate monitor (Garmin watch, chest strap, etc.)."""

    def __init__(self, scan_timeout_sec: int = 5) -> None:
        self._scan_timeout_sec = scan_timeout_sec
        self._loop_thread: AsyncLoopThread | None = None
        if BleakClient and BleakScanner:
            self._loop_thread = AsyncLoopThread()
        self._client: Any | None = None
        self._closing = False
        self._lock = threading.Lock()
        self._snapshot = HRSnapshot()

    @property
    def available(self) -> bool:
        return self._loop_thread is not None

    @property
    def connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    def scan_devices(self) -> list[HRDevice]:
        if not self.available:
            return []
        return self._loop_thread.call(self._scan_devices())

    async def _scan_devices(self) -> list[HRDevice]:
        assert BleakScanner is not None
        found = await BleakScanner.discover(timeout=self._scan_timeout_sec, return_adv=True)
        devices: list[HRDevice] = []
        for device, advertisement in found.values():
            name = device.name or device.address or "BLE-Gerät"
            uuids = {uuid.lower() for uuid in advertisement.service_uuids}
            name_lower = name.lower()
            looks_like_hr = any(token in name_lower for token in HR_NAME_TOKENS)
            if HR_SERVICE_UUID in uuids or looks_like_hr:
                devices.append(HRDevice(identifier=device.address, name=name))
        devices.sort(key=lambda d: (0 if any(t in d.name.lower() for t in GARMIN_NAME_TOKENS) else 1, d.name.lower()))
        return devices

    def connect(self, identifier: str, fallback_name: str | None = None) -> None:
        if not self.available:
            raise RuntimeError("Bleak ist nicht installiert.")
        self._loop_thread.call(self._connect(identifier, fallback_name or identifier))

    async def _connect(self, identifier: str, fallback_name: str) -> None:
        assert BleakClient is not None
        if self._closing:
            raise RuntimeError("HR-Monitor wird bereits beendet.")
        await self._disconnect()
        client = BleakClient(identifier, disconnected_callback=self._handle_disconnect)
        self._client = client
        try:
            await client.connect()
            await client.start_notify(HR_MEASUREMENT_UUID, self._handle_hr_data)
        except BaseException:
            await self._disconnect()
            raise
        self._client = client
        self._set_snapshot(
            connected=True,
            device_name=fallback_name,
            status_text="Verbunden",
        )

    def disconnect(self) -> None:
        if not self.available:
            return
        self._loop_thread.call(self._disconnect(), timeout=10.0)

    async def _disconnect(self) -> None:
        if self._client is None:
            return
        client, self._client = self._client, None
        try:
            if client.is_connected:
                await client.disconnect()
        finally:
            self._set_snapshot(heart_rate=0, connected=False, device_name="Nicht verbunden", status_text="HR nicht verbunden")

    def read_snapshot(self) -> HRSnapshot:
        with self._lock:
            return HRSnapshot(
                heart_rate=self._snapshot.heart_rate,
                connected=self._snapshot.connected,
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
            logger.exception("HR-Monitor konnte beim Beenden nicht sauber getrennt werden.")
        finally:
            self._loop_thread.stop()

    def _set_snapshot(self, **changes: Any) -> None:
        with self._lock:
            current = {
                "heart_rate": self._snapshot.heart_rate,
                "connected": self._snapshot.connected,
                "device_name": self._snapshot.device_name,
                "status_text": self._snapshot.status_text,
            }
            current.update(changes)
            self._snapshot = HRSnapshot(**current)

    def _handle_disconnect(self, _: Any) -> None:
        self._set_snapshot(heart_rate=0, connected=False, device_name="Nicht verbunden", status_text="Verbindung getrennt")

    def _handle_hr_data(self, _: Any, data: bytearray) -> None:
        try:
            hr = parse_hr_measurement(bytes(data))
        except Exception as exc:
            logger.debug("HR-Daten konnten nicht geparst werden: %s", exc)
            return
        self._set_snapshot(heart_rate=hr, connected=True, status_text="Verbunden")


def parse_hr_measurement(payload: bytes) -> int:
    """Parse a BLE Heart Rate Measurement characteristic value."""
    if len(payload) < 2:
        return 0
    flags = payload[0]
    if flags & 0x01:
        # 16-bit HR value
        return struct.unpack_from("<H", payload, 1)[0]
    # 8-bit HR value
    return payload[1]
