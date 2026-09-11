import 'dart:async';

import 'package:cados_ftms_spike/features/trainer/ftms_protocol.dart';
import 'package:cados_ftms_spike/features/trainer/ftms_transport.dart';

class FakeTrainerTransport implements TrainerTransport {
  final scanController = StreamController<FtmsDevice>.broadcast();
  final connectionController =
      StreamController<FtmsConnectionState>.broadcast();
  final measurementController =
      StreamController<IndoorBikeMeasurement>.broadcast();
  final logController = StreamController<String>.broadcast();

  final List<int> sentPower = [];
  bool scanStarted = false;
  bool connected = false;

  @override
  Stream<FtmsDevice> get scanResults => scanController.stream;
  @override
  Stream<FtmsConnectionState> get connectionStates =>
      connectionController.stream;
  @override
  Stream<IndoorBikeMeasurement> get measurements =>
      measurementController.stream;
  @override
  Stream<String> get logs => logController.stream;
  @override
  FtmsPowerRange? powerRange = const FtmsPowerRange(
    minimumWatts: 50,
    maximumWatts: 500,
    incrementWatts: 5,
  );

  @override
  Future<void> startScan() async {
    scanStarted = true;
    logController.add('Scan gestartet');
  }

  @override
  Future<void> stopScan() async => scanStarted = false;

  @override
  Future<void> connect(FtmsDevice device) async {
    connected = true;
    connectionController.add(FtmsConnectionState.connected);
  }

  @override
  Future<void> disconnect() async {
    connected = false;
    connectionController.add(FtmsConnectionState.disconnected);
  }

  FtmsControlResponse _ok(int opcode) =>
      FtmsControlResponse(requestOpcode: opcode, resultCode: 1);

  @override
  Future<FtmsControlResponse> requestControl() async => _ok(0);

  @override
  Future<FtmsControlResponse> setTargetPower(int watts) async {
    sentPower.add(watts);
    return _ok(FtmsOpcode.setTargetPower);
  }

  @override
  Future<FtmsControlResponse> startTraining() async =>
      _ok(FtmsOpcode.startOrResume);
  @override
  Future<FtmsControlResponse> pauseTraining() async =>
      _ok(FtmsOpcode.stopOrPause);
  @override
  Future<FtmsControlResponse> stopTraining() async =>
      _ok(FtmsOpcode.stopOrPause);

  @override
  Future<void> dispose() async {
    await scanController.close();
    await connectionController.close();
    await measurementController.close();
    await logController.close();
  }
}
