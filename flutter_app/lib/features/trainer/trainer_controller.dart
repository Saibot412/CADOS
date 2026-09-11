import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../application/connection_controller.dart';
import '../../core/device.dart';
import '../../core/diagnostic_logger.dart';
import 'ftms_protocol.dart';
import 'ftms_transport.dart';

class TrainerController extends ChangeNotifier {
  TrainerController(
    this.transport, {
    this.logger,
    this.preferences,
    DateTime Function()? now,
  }) : now = now ?? DateTime.now {
    connection = ConnectionController(
      open: (d) => transport.connect(FtmsDevice(id: d.id, name: d.name)),
      close: transport.disconnect,
      log: _log,
    );
    connection.addListener(_connectionChanged);
    _subscriptions.add(transport.scanResults.listen(_onDevice));
    _subscriptions.add(
      transport.connectionStates.listen((value) {
        if (value == FtmsConnectionState.disconnected) {
          measurement = const IndoorBikeMeasurement();
          lastMeasurementAt = null;
          connection.lost();
        }
      }),
    );
    _subscriptions.add(
      transport.measurements.listen((value) {
        if (!connected) return;
        measurement = value;
        lastMeasurementAt = this.now();
        measurementSequence++;
        notifyListeners();
      }),
    );
    _subscriptions.add(
      transport.logs.listen((value) {
        _log(value);
      }),
    );
  }

  final TrainerTransport transport;
  final DateTime Function() now;
  int measurementSequence = 0;
  final DiagnosticLogger? logger;
  final DevicePreferences? preferences;
  late final ConnectionController connection;
  SensorDevice? preferred;
  Timer? _scanTimer;
  int _selectionGeneration = 0;
  Future<void> closed = Future.value();
  bool _disposed = false;
  void _connectionChanged() {
    connectionState = connection.phase == ConnectionPhase.connected
        ? FtmsConnectionState.connected
        : connection.phase == ConnectionPhase.connecting ||
              connection.phase == ConnectionPhase.reconnecting
        ? FtmsConnectionState.connecting
        : FtmsConnectionState.disconnected;
    error = connection.error;
    notifyListeners();
  }

  void _log(String value) {
    logger?.log(value);
    if (logger == null) {
      _fallbackLogs.insert(0, value);
      if (_fallbackLogs.length > 250) _fallbackLogs.removeLast();
    }
    notifyListeners();
  }

  Future<void> restore() async {
    preferred = await preferences?.read('trainer');
    notifyListeners();
  }

  @override
  void notifyListeners() {
    if (!_disposed) super.notifyListeners();
  }

  final List<StreamSubscription<dynamic>> _subscriptions = [];
  final List<FtmsDevice> devices = [];
  final List<String> _fallbackLogs = [];
  List<String> get logs => logger?.lines ?? List.unmodifiable(_fallbackLogs);
  FtmsConnectionState connectionState = FtmsConnectionState.disconnected;
  IndoorBikeMeasurement measurement = const IndoorBikeMeasurement();
  DateTime? lastMeasurementAt;
  FtmsDevice? selectedDevice;
  bool scanning = false;
  bool busy = false;
  String? error;

  FtmsPowerRange? get powerRange => transport.powerRange;
  bool get connected => connectionState == FtmsConnectionState.connected;

  void _onDevice(FtmsDevice device) {
    final index = devices.indexWhere((item) => item.id == device.id);
    if (index == -1) {
      devices.add(device);
    } else {
      devices[index] = device;
    }
    devices.sort((a, b) => (b.rssi ?? -999).compareTo(a.rssi ?? -999));
    notifyListeners();
  }

  Future<void> scan() async {
    if (_disposed || scanning) return;
    await _guard(() async {
      devices.clear();

      scanning = true;
      notifyListeners();
      await transport.startScan();
      if (_disposed || !scanning) {
        await transport.stopScan();
        return;
      }
      _scanTimer?.cancel();
      _scanTimer = Timer(const Duration(seconds: 8), stopScan);
    });
  }

  Future<void> stopScan() async {
    scanning = false;
    _scanTimer?.cancel();
    await _guard(() async {
      await transport.stopScan();
      scanning = false;
    });
  }

  Future<void> connect(FtmsDevice device) async {
    if (_disposed || busy) return;
    final generation = ++_selectionGeneration;
    selectedDevice = device;
    await stopScan();
    if (_disposed || generation != _selectionGeneration) return;
    preferred = SensorDevice(device.id, device.name);
    try {
      await preferences?.save('trainer', preferred!);
    } catch (e) {
      _log('Trainer preference: $e');
    }
    if (_disposed || generation != _selectionGeneration) return;
    await _guard(
      () => connection.connect(SensorDevice(device.id, device.name)),
    );
  }

  Future<void> disconnect() async {
    _selectionGeneration++;
    measurement = const IndoorBikeMeasurement();
    lastMeasurementAt = null;
    await connection.disconnect();
  }

  Future<bool> setPower(int watts) =>
      _command(() => transport.setTargetPower(watts), 'Zielleistung $watts W');
  Future<bool> startTraining() =>
      _command(transport.startTraining, 'Start/Fortsetzen');
  Future<bool> pauseTraining() => _command(transport.pauseTraining, 'Pause');
  Future<bool> stopTraining() => _command(transport.stopTraining, 'Stop');

  Future<bool> _command(
    Future<FtmsControlResponse> Function() action,
    String label,
  ) async {
    if (!connected || busy || _disposed) {
      error = 'Trainer nicht verbunden oder noch beschäftigt.';
      notifyListeners();
      return false;
    }
    busy = true;
    error = null;
    notifyListeners();
    try {
      final response = await action();
      if (!response.successful || !connected || _disposed) {
        throw StateError('$label wurde nicht bestätigt: $response');
      }
      return true;
    } catch (caught) {
      error = '$label fehlgeschlagen: $caught';
      _log(error!);
      return false;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> _guard(Future<void> Function() action) async {
    if (busy || _disposed) return;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await action();
    } catch (caught) {
      error = caught.toString();
      scanning = false;
      _log(error!);
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _scanTimer?.cancel();
    connection.removeListener(_connectionChanged);
    connection.dispose();
    for (final subscription in _subscriptions) {
      subscription.cancel();
    }
    closed = connection.shutdown().then((_) => transport.dispose());
    unawaited(closed);
    super.dispose();
  }
}
