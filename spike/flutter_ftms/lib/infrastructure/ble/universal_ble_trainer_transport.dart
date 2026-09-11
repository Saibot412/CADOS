import 'dart:async';
import 'dart:typed_data';

import 'package:universal_ble/universal_ble.dart';

import '../../features/trainer/ftms_protocol.dart';
import '../../features/trainer/ftms_transport.dart';
import 'scan_coordinator.dart';

class UniversalBleTrainerTransport implements TrainerTransport {
  UniversalBleTrainerTransport(this.scanner) {
    UniversalBle.timeout = const Duration(seconds: 10);
    UniversalBle.queueType = QueueType.perDevice;
    _scanSubscription = UniversalBle.scanStream.listen(
      _handleScanResult,
      onError: (Object error, StackTrace stackTrace) {
        _log('Bluetooth-Scanstream nicht verfügbar: $error');
      },
    );
  }

  final ScanCoordinator scanner;
  final _scanController = StreamController<FtmsDevice>.broadcast();
  final _connectionController =
      StreamController<FtmsConnectionState>.broadcast();
  final _measurementController =
      StreamController<IndoorBikeMeasurement>.broadcast();
  final _logController = StreamController<String>.broadcast();
  final _controlResponses = StreamController<FtmsControlResponse>.broadcast();

  StreamSubscription<BleDevice>? _scanSubscription;

  StreamSubscription<bool>? _connectionSubscription;
  StreamSubscription<Uint8List>? _bikeDataSubscription;
  StreamSubscription<Uint8List>? _controlSubscription;
  BleDevice? _device;
  BleCharacteristic? _bikeData;
  BleCharacteristic? _controlPoint;
  FtmsPowerRange? _powerRange;
  final _seen = <String>{};
  bool _controlGranted = false;
  bool _disposed = false;
  int _measurementCount = 0;

  @override
  Stream<FtmsDevice> get scanResults => _scanController.stream;
  @override
  Stream<FtmsConnectionState> get connectionStates =>
      _connectionController.stream;
  @override
  Stream<IndoorBikeMeasurement> get measurements =>
      _measurementController.stream;
  @override
  Stream<String> get logs => _logController.stream;
  @override
  FtmsPowerRange? get powerRange => _powerRange;

  void _log(String message) {
    if (!_logController.isClosed) {
      _logController.add(message);
    }
  }

  void _handleScanResult(BleDevice device) {
    final hasFtms = device.services.any(
      (uuid) => BleUuidParser.compareStrings(uuid, FtmsUuids.service),
    );
    if (!hasFtms || !_seen.add(device.deviceId)) return;
    final name = (device.name?.trim().isNotEmpty ?? false)
        ? device.name!.trim()
        : 'Unbenannter FTMS-Trainer';
    _scanController.add(
      FtmsDevice(
        id: device.deviceId,
        name: name,
        rssi: device.rssi,
        advertisesFtms: true,
      ),
    );
    _log('Gefunden: $name (${device.rssi ?? 'RSSI unbekannt'} dBm)');
  }

  @override
  Future<void> startScan() async {
    _seen.clear();
    _log('FTMS scan started');
    await scanner.start(this, FtmsUuids.service);
  }

  @override
  Future<void> stopScan() => scanner.stop(this);

  @override
  Future<void> connect(FtmsDevice selected) async {
    await stopScan();
    await disconnect();
    _connectionController.add(FtmsConnectionState.connecting);
    _log('Verbinde mit ${selected.name} …');

    final device = BleDevice(deviceId: selected.id, name: selected.name);
    _device = device;
    _connectionSubscription = device.connectionStream.listen((connected) {
      if (!connected) {
        _controlGranted = false;
        _connectionController.add(FtmsConnectionState.disconnected);
        _log('Bluetooth-Verbindung getrennt');
      }
    });

    try {
      await device.connect(
        autoConnect: false,
        platformConfig: ConnectionPlatformConfig(
          apple: AppleConnectionOptions(
            notifyOnConnection: true,
            notifyOnDisconnection: true,
          ),
          android: AndroidConnectionOptions(closeGattOnDetach: true),
        ),
      );
      final services = await device.discoverServices();
      final service = services.firstWhere(
        (item) => BleUuidParser.compareStrings(item.uuid, FtmsUuids.service),
        orElse: () => throw StateError('Fitness Machine Service 0x1826 fehlt.'),
      );
      _bikeData = _requiredCharacteristic(service, FtmsUuids.indoorBikeData);
      _controlPoint = _requiredCharacteristic(service, FtmsUuids.controlPoint);

      await _readCapabilities(service);
      await _subscribeBikeData();
      await _subscribeControlPoint();
      final response = await requestControl();
      if (!response.successful) {
        throw StateError('Trainer verweigert Steuerung: $response');
      }
      if (!await device.isConnected) {
        throw StateError('Trainer disconnected during setup');
      }
      _controlGranted = true;
      _connectionController.add(FtmsConnectionState.connected);
      _log('FTMS-ERG bereit (${services.length} Services entdeckt)');
    } catch (_) {
      await disconnect();
      rethrow;
    }
  }

  BleCharacteristic _requiredCharacteristic(BleService service, String uuid) {
    return service.characteristics.firstWhere(
      (item) => BleUuidParser.compareStrings(item.uuid, uuid),
      orElse: () => throw StateError('FTMS-Characteristic 0x$uuid fehlt.'),
    );
  }

  BleCharacteristic? _optionalCharacteristic(BleService service, String uuid) {
    for (final characteristic in service.characteristics) {
      if (BleUuidParser.compareStrings(characteristic.uuid, uuid)) {
        return characteristic;
      }
    }
    return null;
  }

  Future<void> _readCapabilities(BleService service) async {
    final feature = _optionalCharacteristic(service, FtmsUuids.feature);
    if (feature != null) {
      try {
        final bytes = await feature.read();
        _log('FTMS Feature: ${_hex(bytes)}');
        if (!FtmsProtocol.supportsTargetPower(bytes)) {
          throw StateError('Der Trainer meldet keine ERG-Zielleistung.');
        }
      } catch (error) {
        if (error is StateError) rethrow;
        _log('Optionale FTMS-Features nicht lesbar: $error');
      }
    }

    final range = _optionalCharacteristic(
      service,
      FtmsUuids.supportedPowerRange,
    );
    if (range != null) {
      try {
        _powerRange = FtmsProtocol.parsePowerRange(await range.read());
        _log(
          'Leistungsbereich: ${_powerRange!.minimumWatts}–'
          '${_powerRange!.maximumWatts} W, Schritt '
          '${_powerRange!.incrementWatts} W',
        );
      } catch (error) {
        _log('Optionaler Leistungsbereich nicht lesbar: $error');
      }
    }
  }

  Future<void> _subscribeBikeData() async {
    final characteristic = _bikeData!;
    _bikeDataSubscription = characteristic.onValueReceived.listen((bytes) {
      try {
        final measurement = FtmsProtocol.parseIndoorBikeData(bytes);
        _measurementCount += 1;
        if (_measurementCount == 1 || _measurementCount % 25 == 0) {
          _log(
            'Indoor Bike Data #$_measurementCount: $measurement '
            '[${_hex(bytes)}]',
          );
        }
        _measurementController.add(measurement);
      } catch (error) {
        _log('Ungültiges Indoor-Bike-Paket ${_hex(bytes)}: $error');
      }
    });
    if (characteristic.notifications.isSupported) {
      await characteristic.notifications.subscribe();
    } else if (characteristic.indications.isSupported) {
      await characteristic.indications.subscribe();
    } else {
      throw StateError('Indoor Bike Data unterstützt keine Updates.');
    }
    _log('Indoor Bike Data abonniert');
  }

  Future<void> _subscribeControlPoint() async {
    final characteristic = _controlPoint!;
    _controlSubscription = characteristic.onValueReceived.listen((bytes) {
      final response = FtmsProtocol.parseControlResponse(bytes);
      if (response == null) {
        _log('Unbekannte Control-Antwort: ${_hex(bytes)}');
        return;
      }
      _log('Control-Antwort: $response [${_hex(bytes)}]');
      _controlResponses.add(response);
    });
    if (characteristic.indications.isSupported) {
      await characteristic.indications.subscribe();
    } else if (characteristic.notifications.isSupported) {
      await characteristic.notifications.subscribe();
    } else {
      throw StateError('FTMS Control Point unterstützt keine Antworten.');
    }
    _log('FTMS Control Point abonniert');
  }

  @override
  Future<FtmsControlResponse> requestControl() async {
    final response = await _writeControl(FtmsProtocol.requestControl());
    _controlGranted = response.successful;
    return response;
  }

  @override
  Future<FtmsControlResponse> setTargetPower(int watts) async {
    await _ensureControl();
    final target = _powerRange?.clampAndRound(watts) ?? watts;
    _log('Sende Zielleistung: $target W');
    return _writeControl(FtmsProtocol.setTargetPower(target));
  }

  @override
  Future<FtmsControlResponse> startTraining() async {
    await _ensureControl();
    _log('Sende Start/Fortsetzen');
    return _writeControl(FtmsProtocol.start());
  }

  @override
  Future<FtmsControlResponse> pauseTraining() async {
    await _ensureControl();
    _log('Sende Pause');
    return _writeControl(FtmsProtocol.pause());
  }

  @override
  Future<FtmsControlResponse> stopTraining() async {
    await _ensureControl();
    _log('Sende Stop');
    return _writeControl(FtmsProtocol.stop());
  }

  Future<void> _ensureControl() async {
    if (_controlGranted) return;
    final response = await requestControl();
    if (!response.successful) {
      throw StateError('Keine FTMS-Steuerfreigabe: $response');
    }
  }

  Future<FtmsControlResponse> _writeControl(List<int> payload) async {
    final characteristic = _controlPoint;
    if (characteristic == null) throw StateError('Kein Trainer verbunden.');
    final opcode = payload.first;
    final responseFuture = _controlResponses.stream
        .firstWhere((response) => response.requestOpcode == opcode)
        .timeout(const Duration(seconds: 5));
    _log('Control Write: ${_hex(payload)}');
    // Attach immediately: the response timeout may precede a slow write failure.
    unawaited(responseFuture.then<void>((_) {}, onError: (Object _) {}));
    await characteristic.write(payload, withResponse: true);
    return responseFuture;
  }

  @override
  Future<void> disconnect() async {
    _controlGranted = false;
    _powerRange = null;
    await _bikeDataSubscription?.cancel();
    await _controlSubscription?.cancel();
    await _connectionSubscription?.cancel();
    _bikeDataSubscription = null;
    _controlSubscription = null;
    _connectionSubscription = null;
    _bikeData = null;
    _controlPoint = null;
    final device = _device;
    _device = null;
    if (device != null) {
      try {
        if (await device.isConnected) await device.disconnect();
      } catch (error) {
        _log('Trennen meldete: $error');
      }
    }
  }

  static String _hex(Iterable<int> bytes) =>
      bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join(' ');

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    try {
      await stopScan();
    } catch (e) {
      _log("Scan shutdown: $e");
    }
    await disconnect();
    _disposed = true;
    await _scanSubscription?.cancel();

    await _scanController.close();
    await _connectionController.close();
    await _measurementController.close();
    await _controlResponses.close();
    await _logController.close();
  }
}
