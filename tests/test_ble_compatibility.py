import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cados.services.trainer import FtmsBluetoothService
from cados.services.hr_monitor import HRMonitorService, parse_hr_measurement, HR_SERVICE_UUID


def trainer_service():
    with patch('cados.services.trainer.BleakClient', None):
        return FtmsBluetoothService()


class BLEPacketTests(unittest.TestCase):
    def test_split_ftms_packets_preserve_cadence_and_expire_without_false_zero(self):
        service = trainer_service()
        service._ready_for_control = True
        with patch('cados.services.trainer.time.monotonic', return_value=10):
            service._handle_indoor_bike_data(None,bytearray(struct.pack('<HHHh',68,200,180,300)))
            # Continuation packet only carries power; absent cadence is not zero.
            service._handle_indoor_bike_data(None,bytearray(struct.pack('<Hh',65,310)))
            snapshot=service.read_snapshot()
            self.assertEqual((snapshot.current_watts,snapshot.cadence),(310,90))
            self.assertTrue(snapshot.cadence_available)
            service._handle_indoor_bike_data(None,bytearray(struct.pack('<HH',5,0)))
            self.assertEqual(service.read_snapshot().cadence,0)
            self.assertTrue(service.read_snapshot().cadence_available)
        with patch('cados.services.trainer.time.monotonic', return_value=16):
            snapshot=service.read_snapshot()
            self.assertFalse(snapshot.connected)
            self.assertFalse(snapshot.cadence_available)

    def test_truncated_ftms_packet_does_not_replace_valid_measurements(self):
        service=trainer_service()
        service._handle_indoor_bike_data(None,bytearray(struct.pack('<HHHh',68,200,180,300)))
        service._handle_indoor_bike_data(None,bytearray(struct.pack('<H',68)))
        self.assertEqual(service.read_snapshot().current_watts,300)
        with self.assertRaises(ValueError):
            service._parse_indoor_bike_data(b'')

    def test_power_limits_and_supported_step(self):
        service=trainer_service()
        service._loop_thread=SimpleNamespace(call=asyncio.run)
        service._client=SimpleNamespace(is_connected=True)
        service._ready_for_control=True
        service._set_snapshot(min_power=50,max_power=1000,power_step=5)
        service._run_control_command=AsyncMock(return_value=1)
        self.assertTrue(service.set_target_power(1500))
        self.assertEqual(service._run_control_command.call_args.args[0],b'\x05'+struct.pack('<h',1000))
        service.set_target_power(302)
        self.assertEqual(service._run_control_command.call_args.args[0],b'\x05'+struct.pack('<h',300))

    def test_hr_8_and_16_bit_contact_energy_rr(self):
        self.assertEqual(parse_hr_measurement(bytes([0,150])),150)
        self.assertEqual(parse_hr_measurement(bytes([1,180,0])),180)
        self.assertEqual(parse_hr_measurement(bytes([30,160,0,0,0,4])),160)
        self.assertIsNone(parse_hr_measurement(bytes([4,160])))
        self.assertIsNone(parse_hr_measurement(bytes([0,255])))
        for packet in (b'',b'\x01\x80',b'\x10\x80\x01'):
            with self.assertRaises(ValueError):parse_hr_measurement(packet)

    def test_stale_hr_is_not_reused_as_current_measurement(self):
        with patch('cados.services.hr_monitor.BleakClient',None):
            service=HRMonitorService()
        with patch('cados.services.hr_monitor.time.monotonic',return_value=10):
            service._handle_hr_data(None,bytearray([0,140]))
            self.assertEqual(service.read_snapshot().heart_rate,140)
        with patch('cados.services.hr_monitor.time.monotonic',return_value=21):
            self.assertEqual(service.read_snapshot().heart_rate,0)
            self.assertFalse(service.read_snapshot().data_available)


class BLEDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_brand_and_short_uuid_are_discovered(self):
        device=SimpleNamespace(name=None,address='test')
        adv=SimpleNamespace(local_name='New Brand Bike',service_uuids=['1826'],rssi=-42)
        service=trainer_service()
        with patch('cados.services.trainer.BleakScanner',SimpleNamespace(discover=AsyncMock(return_value={'test':(device,adv)}))):
            devices=await service._scan_devices()
        self.assertEqual(devices[0].name,'New Brand Bike')
        self.assertEqual(devices[0].protocol,'Bluetooth FTMS')
        self.assertIs(service._seen_devices['test'],device)

    async def test_unknown_hr_sensor_uses_service_not_brand(self):
        with patch('cados.services.hr_monitor.BleakClient',None):
            service=HRMonitorService()
        device=SimpleNamespace(name='New Optical Sensor',address='test')
        adv=SimpleNamespace(service_uuids=['180D'])
        with patch('cados.services.hr_monitor.BleakScanner',SimpleNamespace(discover=AsyncMock(return_value={'test':(device,adv)}))):
            devices=await service._scan_devices()
        self.assertEqual(devices[0].protocol,'Bluetooth Herzfrequenz')

    async def test_ftms_without_erg_capability_is_rejected(self):
        service=trainer_service()
        client=SimpleNamespace(is_connected=True,connect=AsyncMock(),disconnect=AsyncMock(),
            services=SimpleNamespace(get_characteristic=lambda uuid: object()),read_gatt_char=AsyncMock(return_value=bytes(8)))
        with patch('cados.services.trainer.BleakClient',return_value=client):
            with self.assertRaisesRegex(RuntimeError,'ERG'):
                await service._connect('test','Test')
        client.disconnect.assert_awaited_once()
        self.assertFalse(service.connected)
