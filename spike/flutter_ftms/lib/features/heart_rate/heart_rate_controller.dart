import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../application/connection_controller.dart';
import '../../core/device.dart';
import '../../core/diagnostic_logger.dart';
import 'heart_rate.dart';

class HeartRateController extends ChangeNotifier {
  HeartRateController(this.transport, this.logger, this.preferences) {
    connection = ConnectionController(
      open: transport.connect,
      close: transport.disconnect,
      log: logger.log,
    );
    connection.addListener(_changed);
    _subscriptions.addAll([
      transport.devices.listen((d) {
        devices.removeWhere((v) => v.id == d.id);
        devices.add(d);
        notifyListeners();
      }),
      transport.measurements.listen((m) {
        if (connection.phase != ConnectionPhase.connected) return;
        measurement = m;
        notifyListeners();
      }),
      transport.disconnections.listen((_) {
        measurement = null;
        connection.lost();
      }),
      transport.logs.listen(logger.log),
    ]);
  }
  final HeartRateTransport transport;
  final DiagnosticLogger logger;
  final DevicePreferences preferences;
  late final ConnectionController connection;
  final List<StreamSubscription<dynamic>> _subscriptions = [];
  final List<SensorDevice> devices = [];
  HeartRateMeasurement? measurement;
  SensorDevice? preferred;
  bool scanning = false, _disposed = false;
  String? error;
  Timer? _scanTimer;
  int _selectionGeneration = 0;
  Future<void> closed = Future.value();
  void _changed() {
    if (!_disposed) notifyListeners();
  }

  Future<void> restore() async {
    preferred = await preferences.read('heart_rate');
    _changed();
  }

  Future<void> scan() async {
    if (_disposed || scanning) return;
    error = null;
    try {
      scanning = true;
      _changed();
      await transport.scan();
      if (_disposed || !scanning) {
        await transport.stopScan();
        return;
      }
      _scanTimer?.cancel();
      _scanTimer = Timer(const Duration(seconds: 8), stopScan);
    } catch (e) {
      error = '$e';
      logger.log('HR scan: $e');
      scanning = false;
    }
    _changed();
  }

  Future<void> stopScan() async {
    scanning = false;
    _scanTimer?.cancel();
    try {
      await transport.stopScan();
    } catch (e) {
      error = '$e';
      logger.log('HR scan stop: $e');
    }
    scanning = false;
    _changed();
  }

  Future<void> connect(SensorDevice d) async {
    final generation = ++_selectionGeneration;
    await stopScan();
    if (_disposed || generation != _selectionGeneration) return;
    preferred = d;
    try {
      await preferences.save('heart_rate', d);
    } catch (e) {
      logger.log('HR preference: $e');
    }
    if (_disposed || generation != _selectionGeneration) return;
    error = null;
    await connection.connect(d);
  }

  Future<void> disconnect() async {
    _selectionGeneration++;
    measurement = null;
    await connection.disconnect();
  }

  @override
  void dispose() {
    _disposed = true;
    _scanTimer?.cancel();
    connection.removeListener(_changed);
    connection.dispose();
    for (final s in _subscriptions) {
      unawaited(s.cancel());
    }
    closed = connection.shutdown().then((_) => transport.dispose());
    unawaited(closed);
    super.dispose();
  }
}
