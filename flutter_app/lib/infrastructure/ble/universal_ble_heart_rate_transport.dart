import 'dart:async';

import 'package:universal_ble/universal_ble.dart';

import '../../core/device.dart';
import '../../features/heart_rate/heart_rate.dart';
import 'scan_coordinator.dart';

class UniversalBleHeartRateTransport implements HeartRateTransport {
  UniversalBleHeartRateTransport(this.scanner) {
    _scan = UniversalBle.scanStream.listen(
      (d) {
        if (d.services.any((s) => BleUuidParser.compareStrings(s, '180d'))) {
          _devices.add(SensorDevice(d.deviceId, d.name ?? 'HR sensor'));
        }
      },
      onError: (Object error, StackTrace stackTrace) {
        _logs.add('HR Bluetooth-Scanstream nicht verfügbar: $error');
      },
    );
  }
  final ScanCoordinator scanner;
  final _devices = StreamController<SensorDevice>.broadcast();
  final _measurements = StreamController<HeartRateMeasurement>.broadcast();
  final _lost = StreamController<void>.broadcast();
  final _logs = StreamController<String>.broadcast();
  StreamSubscription<dynamic>? _scan, _connection, _data;
  BleDevice? _device;
  @override
  Stream<SensorDevice> get devices => _devices.stream;
  @override
  Stream<HeartRateMeasurement> get measurements => _measurements.stream;
  @override
  Stream<void> get disconnections => _lost.stream;
  @override
  Stream<String> get logs => _logs.stream;
  @override
  Future<void> scan() async {
    await scanner.start(this, '180d');
  }

  @override
  Future<void> stopScan() => scanner.stop(this);

  @override
  Future<void> connect(SensorDevice selected) async {
    await stopScan();
    await disconnect();
    final device = BleDevice(deviceId: selected.id, name: selected.name);
    _device = device;
    _connection = device.connectionStream.listen((connected) {
      if (!connected) _lost.add(null);
    });
    try {
      await device.connect(autoConnect: false);
      final services = await device.discoverServices();
      final service = services.firstWhere(
        (s) => BleUuidParser.compareStrings(s.uuid, '180d'),
      );
      final characteristic = service.characteristics.firstWhere(
        (c) => BleUuidParser.compareStrings(c.uuid, '2a37'),
      );
      _data = characteristic.onValueReceived.listen((bytes) {
        try {
          _measurements.add(HeartRateMeasurement.parse(bytes));
        } catch (e) {
          _logs.add('Invalid HR measurement: $e');
        }
      });
      await characteristic.notifications.subscribe();
      if (!await device.isConnected) {
        throw StateError('HR disconnected during setup');
      }
    } catch (_) {
      await disconnect();
      rethrow;
    }
  }

  @override
  Future<void> disconnect() async {
    await _connection?.cancel();
    await _data?.cancel();
    _connection = null;
    _data = null;
    final device = _device;
    _device = null;
    if (device != null) {
      try {
        await device.disconnect();
      } catch (e) {
        _logs.add('HR disconnect: $e');
      }
    }
  }

  @override
  Future<void> dispose() async {
    try {
      await stopScan();
    } catch (e) {
      _logs.add("HR scan shutdown: $e");
    }
    await _scan?.cancel();

    await disconnect();
    await _devices.close();
    await _measurements.close();
    await _lost.close();
    await _logs.close();
  }
}
