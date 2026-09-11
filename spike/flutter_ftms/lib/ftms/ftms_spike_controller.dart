import 'dart:async';

import 'package:flutter/foundation.dart';

import 'ftms_protocol.dart';
import 'ftms_transport.dart';

class FtmsSpikeController extends ChangeNotifier {
  FtmsSpikeController(this.transport) {
    _subscriptions.add(transport.scanResults.listen(_onDevice));
    _subscriptions.add(
      transport.connectionStates.listen((value) {
        connectionState = value;
        notifyListeners();
      }),
    );
    _subscriptions.add(
      transport.measurements.listen((value) {
        measurement = value;
        lastMeasurementAt = DateTime.now();
        notifyListeners();
      }),
    );
    _subscriptions.add(
      transport.logs.listen((value) {
        logs.insert(0, value);
        if (logs.length > 250) logs.removeLast();
        notifyListeners();
      }),
    );
  }

  final TrainerTransport transport;
  final List<StreamSubscription<dynamic>> _subscriptions = [];
  final List<FtmsDevice> devices = [];
  final List<String> logs = [];
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
    await _guard(() async {
      devices.clear();
      selectedDevice = null;
      scanning = true;
      notifyListeners();
      await transport.startScan();
      await Future<void>.delayed(const Duration(seconds: 8));
      await transport.stopScan();
      scanning = false;
      notifyListeners();
    });
  }

  Future<void> stopScan() async {
    await _guard(() async {
      await transport.stopScan();
      scanning = false;
    });
  }

  Future<void> connect(FtmsDevice device) async {
    selectedDevice = device;
    await _guard(() => transport.connect(device));
  }

  Future<void> disconnect() => _guard(transport.disconnect);

  Future<void> setPower(int watts) =>
      _command(() => transport.setTargetPower(watts), 'Zielleistung $watts W');
  Future<void> startTraining() =>
      _command(transport.startTraining, 'Start/Fortsetzen');
  Future<void> pauseTraining() => _command(transport.pauseTraining, 'Pause');
  Future<void> stopTraining() => _command(transport.stopTraining, 'Stop');

  Future<void> _command(
    Future<FtmsControlResponse> Function() action,
    String label,
  ) async {
    await _guard(() async {
      final response = await action();
      if (!response.successful) throw StateError('$label: $response');
    });
  }

  Future<void> _guard(Future<void> Function() action) async {
    if (busy) return;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await action();
    } catch (caught) {
      error = caught.toString();
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    for (final subscription in _subscriptions) {
      subscription.cancel();
    }
    transport.dispose();
    super.dispose();
  }
}
