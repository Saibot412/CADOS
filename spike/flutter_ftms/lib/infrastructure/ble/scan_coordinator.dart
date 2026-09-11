import 'package:universal_ble/universal_ble.dart';

/// Owns the adapter-wide scan, including asynchronous permission/start work.
class ScanCoordinator {
  ScanCoordinator({
    Future<void> Function(String)? startScan,
    Future<void> Function()? stopScan,
  }) : _startScan = startScan ?? _startPluginScan,
       _stopScan = stopScan ?? _stopPluginScan;
  final Future<void> Function(String) _startScan;
  final Future<void> Function() _stopScan;
  Object? _owner;
  Future<void>? _starting;
  Future<void> start(Object owner, String service) async {
    if (_owner != null) {
      throw StateError(
        'Ein Bluetooth-Scan läuft bereits. Bitte zuerst stoppen.',
      );
    }
    _owner = owner;
    final operation = _startScan(service);
    _starting = operation.then<void>((_) {}, onError: (Object _) {});
    try {
      await operation;
    } catch (_) {
      if (identical(_owner, owner)) _owner = null;
      rethrow;
    }
  }

  Future<void> stop(Object owner) async {
    if (!identical(_owner, owner)) return;
    await _starting;
    if (!identical(_owner, owner)) return;
    try {
      await _stopScan();
    } finally {
      if (identical(_owner, owner)) _owner = null;
    }
  }

  static Future<void> _startPluginScan(String service) async {
    await UniversalBle.requestPermissions();
    final state = await UniversalBle.getBluetoothAvailabilityState();
    if (state != AvailabilityState.poweredOn) {
      throw StateError('Bluetooth unavailable: $state');
    }
    await UniversalBle.startScan(
      scanFilter: ScanFilter(withServices: [service]),
      platformConfig: PlatformConfig(
        web: WebOptions(optionalServices: [service]),
      ),
    );
  }

  static Future<void> _stopPluginScan() async {
    if (await UniversalBle.isScanning()) await UniversalBle.stopScan();
  }
}
