from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cados.services.trainer import FtmsBluetoothService, TrainerController, TrainerDevice


class _FakeClient:
    def __init__(self) -> None:
        self.is_connected = True
        self.writes: list[bytes] = []

    async def write_gatt_char(self, _uuid: str, payload: bytes, response: bool = True) -> None:
        self.writes.append(payload)


class FtmsBluetoothServiceTests(unittest.IsolatedAsyncioTestCase):
    def make_service(self):
        with patch("cados.services.trainer.BleakClient", None):
            return FtmsBluetoothService()

    async def test_mismatched_indication_cannot_acknowledge_a_command(self):
        service = self.make_service()
        service._client = _FakeClient()
        task = asyncio.create_task(service._write_control(bytes([service.REQUEST_CONTROL])))
        await asyncio.sleep(0)
        service._handle_control_point_response(None, bytearray([0x80, service.SET_TARGET_POWER, 1]))
        self.assertFalse(service._pending_control_response.done())
        service._handle_control_point_response(None, bytearray([0x80, service.REQUEST_CONTROL, 1]))
        self.assertEqual(await task, 1)

    async def test_control_commands_are_serialized_until_acknowledged(self):
        service = self.make_service()
        service._client = _FakeClient()
        service._control_granted = True
        first = asyncio.create_task(service._run_control_command(bytes([service.START_OR_RESUME])))
        second = asyncio.create_task(service._run_control_command(bytes([service.STOP_OR_PAUSE, service.STOP])))
        await asyncio.sleep(0)
        self.assertEqual(len(service._client.writes), 1)
        service._handle_control_point_response(None, bytearray([0x80, service.START_OR_RESUME, 1]))
        self.assertEqual(await first, 1)
        await asyncio.sleep(0)
        self.assertEqual(len(service._client.writes), 2)
        service._handle_control_point_response(None, bytearray([0x80, service.STOP_OR_PAUSE, 1]))
        self.assertEqual(await second, 1)

    async def test_failed_control_subscription_disconnects_partial_connection(self):
        service = self.make_service()
        client = SimpleNamespace(is_connected=True, connect=AsyncMock(), disconnect=AsyncMock(),
                                 start_notify=AsyncMock(side_effect=[None, RuntimeError("no indications")]))
        with patch("cados.services.trainer.BleakClient", return_value=client):
            with self.assertRaises(RuntimeError):
                await service._connect("fake", "Fake Trainer")
        client.disconnect.assert_awaited_once()
        self.assertFalse(service.connected)
        self.assertIsNone(service._client)

    async def test_discovery_uses_advertisement_service_uuids(self):
        service = self.make_service()
        device = SimpleNamespace(name="Elite Direto", address="fake")
        adv = SimpleNamespace(service_uuids=[service.FTMS_SERVICE_UUID])
        discover = AsyncMock(return_value={"fake": (device, adv)})
        with patch("cados.services.trainer.BleakScanner", SimpleNamespace(discover=discover)):
            devices = await service._scan_devices()
        self.assertEqual([d.name for d in devices], ["Elite Direto"])
        discover.assert_awaited_once_with(timeout=5, return_adv=True)

    def test_parse_indoor_bike_data_reads_cadence_and_power(self) -> None:
        flags = (1 << 2) | (1 << 6)
        payload = (
            flags.to_bytes(2, "little")
            + (300).to_bytes(2, "little")   # instantaneous speed
            + (180).to_bytes(2, "little")   # cadence in 0.5 rpm
            + (250).to_bytes(2, "little", signed=True)
        )

        power, cadence = FtmsBluetoothService._parse_indoor_bike_data(payload)

        self.assertEqual(power, 250)
        self.assertEqual(cadence, 90)

    async def test_write_control_waits_for_indication(self) -> None:
        service = FtmsBluetoothService()
        try:
            service._client = _FakeClient()

            async def respond() -> None:
                await asyncio.sleep(0)
                service._handle_control_point_response(None, bytearray([service.RESPONSE_CODE, service.REQUEST_CONTROL, 0x01]))

            responder = asyncio.create_task(respond())
            result = await service._write_control(bytes([service.REQUEST_CONTROL]))
            await responder

            self.assertEqual(result, 0x01)
            self.assertTrue(service._control_granted)
            self.assertEqual(service._client.writes, [bytes([service.REQUEST_CONTROL])])
        finally:
            service._client = None
            service.close()


class TrainerControllerTests(unittest.TestCase):
    def test_pick_preferred_device_prefers_wahoo_and_kickr(self) -> None:
        devices = [
            TrainerDevice(identifier="other", name="Elite Direto"),
            TrainerDevice(identifier="wahoo", name="Wahoo KICKR CORE"),
        ]

        preferred = TrainerController.pick_preferred_device(devices)

        self.assertIsNotNone(preferred)
        assert preferred is not None
        self.assertEqual(preferred.identifier, "wahoo")


if __name__ == "__main__":
    unittest.main()
