import 'dart:async';

import 'ftms_protocol.dart';

class FtmsDevice {
  const FtmsDevice({
    required this.id,
    required this.name,
    this.rssi,
    this.advertisesFtms = false,
  });

  final String id;
  final String name;
  final int? rssi;
  final bool advertisesFtms;
}

enum FtmsConnectionState { disconnected, connecting, connected }

abstract interface class TrainerTransport {
  Stream<FtmsDevice> get scanResults;
  Stream<FtmsConnectionState> get connectionStates;
  Stream<IndoorBikeMeasurement> get measurements;
  Stream<String> get logs;
  FtmsPowerRange? get powerRange;

  Future<void> startScan();
  Future<void> stopScan();
  Future<void> connect(FtmsDevice device);
  Future<void> disconnect();
  Future<FtmsControlResponse> requestControl();
  Future<FtmsControlResponse> setTargetPower(int watts);
  Future<FtmsControlResponse> startTraining();
  Future<FtmsControlResponse> pauseTraining();
  Future<FtmsControlResponse> stopTraining();
  Future<void> dispose();
}
