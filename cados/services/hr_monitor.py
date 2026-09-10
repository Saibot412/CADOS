from __future__ import annotations

import logging
import struct
import threading
import time
from dataclasses import dataclass, replace
from typing import Any

from cados.services.async_loop import AsyncLoopThread
from cados.services.ble_devices import advertisement_info, HR_NAMES

logger = logging.getLogger(__name__)

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # pragma: no cover - optional dependency at runtime
    BleakClient = None
    BleakScanner = None


HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

GARMIN_NAME_TOKENS = ("garmin", "forerunner", "fenix", "venu", "vivoactive", "enduro", "instinct", "epix")
HR_NAME_TOKENS = HR_NAMES


@dataclass(slots=True)
class HRDevice:
    identifier: str
    name: str
    protocol: str = "Prüfung beim Verbinden"
    rssi: int | None = None


@dataclass(slots=True)
class HRSnapshot:
    heart_rate: int = 0
    connected: bool = False
    device_name: str = "Nicht verbunden"
    status_text: str = "HR-Monitor nicht verbunden"
    data_available: bool = False


class HRMonitorService:
    """Connects to a BLE Heart Rate monitor (Garmin watch, chest strap, etc.)."""

    def __init__(self, scan_timeout_sec: int = 5) -> None:
        self._scan_timeout_sec = scan_timeout_sec
        self._loop_thread: AsyncLoopThread | None = None
        if BleakClient and BleakScanner:
            self._loop_thread = AsyncLoopThread()
        self._seen_devices = {}
        self._measurement_at = None
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
        self._seen_devices = {}
        for device, advertisement in found.values():
            name, uuids, rssi = advertisement_info(device, advertisement)
            standard = HR_SERVICE_UUID in uuids
            if standard or any(token in name.casefold() for token in HR_NAME_TOKENS):
                self._seen_devices[device.address] = device
                devices.append(HRDevice(device.address, name, "Bluetooth Herzfrequenz" if standard else "Sendemodus prüfen", rssi))
        devices.sort(key=lambda d: (0 if d.protocol == 'Bluetooth Herzfrequenz' else 1, d.name.casefold()))
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
        client = BleakClient(self._seen_devices.get(identifier, identifier), disconnected_callback=lambda sender: self._handle_disconnect(sender) if self._client is sender else None)
        self._client = client
        try:
            await client.connect()
            if not client.services.get_characteristic(HR_MEASUREMENT_UUID):
                raise RuntimeError("Dieses Gerät sendet kein Bluetooth-Pulssignal. Bei Uhren zuerst Herzfrequenz senden / Broadcast HR aktivieren. ANT+-only und Apple Watch werden nicht direkt unterstützt.")
            await client.start_notify(HR_MEASUREMENT_UUID, lambda sender, data: self._handle_hr_data(sender, data) if self._client is client else None)
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
        self._measurement_at = None
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
            snapshot = replace(self._snapshot)
            snapshot.data_available = snapshot.connected and self._measurement_at is not None and time.monotonic() - self._measurement_at <= 10
            if not snapshot.data_available:
                snapshot.heart_rate = 0
                if snapshot.connected:
                    snapshot.status_text = "Verbunden – warte auf aktuellen Puls / Hautkontakt"
            return snapshot

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
        with self._lock:
            self._measurement_at = time.monotonic() if hr is not None else None
            self._snapshot = replace(self._snapshot, heart_rate=hr or 0, connected=True, status_text="Verbunden")


def parse_hr_measurement(payload: bytes) -> int | None:
    """BLE HRS: 8/16-bit BPM, optional contact status, energy and RR intervals."""
    if len(payload) < 2:
        raise ValueError("Unvollständiges Pulssignal")
    flags = payload[0]
    size = 2 if flags & 1 else 1
    if len(payload) < 1 + size:
        raise ValueError("Unvollständiger 16-Bit-Pulswert")
    hr = int.from_bytes(payload[1:1 + size], 'little')
    offset = 1 + size
    if flags & 8:
        offset += 2
    if len(payload) < offset or (flags & 16 and (len(payload) == offset or (len(payload) - offset) % 2)):
        raise ValueError("Unvollständige optionale Pulsmessdaten")
    if flags & 4 and not flags & 2:
        return None  # Sensor explicitly reports no skin contact.
    return hr if 0 < hr <= 250 else None
