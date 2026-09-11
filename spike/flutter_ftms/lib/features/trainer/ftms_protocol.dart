import 'dart:typed_data';

abstract final class FtmsUuids {
  static const service = '1826';
  static const feature = '2acc';
  static const indoorBikeData = '2ad2';
  static const supportedPowerRange = '2ad8';
  static const controlPoint = '2ad9';
  static const status = '2ada';
}

abstract final class FtmsOpcode {
  static const requestControl = 0x00;
  static const setTargetPower = 0x05;
  static const startOrResume = 0x07;
  static const stopOrPause = 0x08;
  static const responseCode = 0x80;
}

abstract final class FtmsResultCode {
  static const success = 0x01;

  static String label(int code) => switch (code) {
    0x01 => 'Erfolg',
    0x02 => 'Opcode nicht unterstützt',
    0x03 => 'Ungültiger Parameter',
    0x04 => 'Operation fehlgeschlagen',
    0x05 => 'Steuerung nicht erlaubt',
    _ => 'Unbekannter Code 0x${code.toRadixString(16).padLeft(2, '0')}',
  };
}

class IndoorBikeMeasurement {
  const IndoorBikeMeasurement({this.powerWatts, this.cadenceRpm});

  final int? powerWatts;
  final double? cadenceRpm;

  @override
  String toString() =>
      'Leistung: ${powerWatts ?? '–'} W, '
      'Kadenz: ${cadenceRpm?.toStringAsFixed(1) ?? '–'} rpm';
}

class FtmsPowerRange {
  const FtmsPowerRange({
    required this.minimumWatts,
    required this.maximumWatts,
    required this.incrementWatts,
  });

  final int minimumWatts;
  final int maximumWatts;
  final int incrementWatts;

  int clampAndRound(int watts) {
    final clamped = watts.clamp(minimumWatts, maximumWatts);
    if (incrementWatts <= 0) return clamped;
    final steps = ((clamped - minimumWatts) / incrementWatts).round();
    return (minimumWatts + steps * incrementWatts).clamp(
      minimumWatts,
      maximumWatts,
    );
  }
}

class FtmsControlResponse {
  const FtmsControlResponse({
    required this.requestOpcode,
    required this.resultCode,
  });

  final int requestOpcode;
  final int resultCode;
  bool get successful => resultCode == FtmsResultCode.success;

  @override
  String toString() =>
      'Op 0x${requestOpcode.toRadixString(16).padLeft(2, '0')}: '
      '${FtmsResultCode.label(resultCode)}';
}

class FtmsProtocolException implements Exception {
  const FtmsProtocolException(this.message);
  final String message;
  @override
  String toString() => message;
}

abstract final class FtmsProtocol {
  static IndoorBikeMeasurement parseIndoorBikeData(List<int> bytes) {
    if (bytes.length < 2) {
      throw const FtmsProtocolException('FTMS-Flags fehlen');
    }
    final data = Uint8List.fromList(bytes);
    final view = ByteData.sublistView(data);
    final flags = view.getUint16(0, Endian.little);
    var offset = 2;

    void skip(int size) {
      if (offset + size > data.length) {
        throw const FtmsProtocolException('FTMS-Datenpaket unvollständig');
      }
      offset += size;
    }

    int uint16() {
      if (offset + 2 > data.length) {
        throw const FtmsProtocolException('FTMS-Datenpaket unvollständig');
      }
      final value = view.getUint16(offset, Endian.little);
      offset += 2;
      return value;
    }

    int int16() {
      if (offset + 2 > data.length) {
        throw const FtmsProtocolException('FTMS-Datenpaket unvollständig');
      }
      final value = view.getInt16(offset, Endian.little);
      offset += 2;
      return value;
    }

    if (flags & 1 == 0) skip(2); // Instantaneous speed.
    if (flags & (1 << 1) != 0) skip(2); // Average speed.
    final cadence = flags & (1 << 2) != 0 ? uint16() / 2.0 : null;
    for (final field in const [(3, 2), (4, 3), (5, 2)]) {
      if (flags & (1 << field.$1) != 0) skip(field.$2);
    }
    final power = flags & (1 << 6) != 0 ? int16() : null;
    for (final field in const [
      (7, 2),
      (8, 5),
      (9, 1),
      (10, 1),
      (11, 2),
      (12, 2),
    ]) {
      if (flags & (1 << field.$1) != 0) skip(field.$2);
    }
    return IndoorBikeMeasurement(powerWatts: power, cadenceRpm: cadence);
  }

  static FtmsPowerRange parsePowerRange(List<int> bytes) {
    if (bytes.length < 6) {
      throw const FtmsProtocolException('Leistungsbereich ist unvollständig');
    }
    final view = ByteData.sublistView(Uint8List.fromList(bytes));
    final result = FtmsPowerRange(
      minimumWatts: view.getInt16(0, Endian.little),
      maximumWatts: view.getInt16(2, Endian.little),
      incrementWatts: view.getUint16(4, Endian.little),
    );
    if (result.minimumWatts >= result.maximumWatts ||
        result.maximumWatts <= 0 ||
        result.incrementWatts <= 0) {
      throw const FtmsProtocolException('Leistungsbereich ist ungültig');
    }
    return result;
  }

  static bool supportsTargetPower(List<int> bytes) {
    if (bytes.length != 8) return true; // Unknown: do not reject optional data.
    final targetFeatures = ByteData.sublistView(Uint8List.fromList(bytes))
        .getUint32(4, Endian.little);
    return targetFeatures & (1 << 3) != 0;
  }

  static FtmsControlResponse? parseControlResponse(List<int> bytes) {
    if (bytes.length < 3 || bytes.first != FtmsOpcode.responseCode) return null;
    return FtmsControlResponse(requestOpcode: bytes[1], resultCode: bytes[2]);
  }

  static List<int> requestControl() => const [FtmsOpcode.requestControl];
  static List<int> start() => const [FtmsOpcode.startOrResume];
  static List<int> pause() => const [FtmsOpcode.stopOrPause, 0x02];
  static List<int> stop() => const [FtmsOpcode.stopOrPause, 0x01];

  static List<int> setTargetPower(int watts) {
    if (watts < -32768 || watts > 32767) {
      throw RangeError.range(watts, -32768, 32767, 'watts');
    }
    final data = ByteData(3)
      ..setUint8(0, FtmsOpcode.setTargetPower)
      ..setInt16(1, watts, Endian.little);
    return data.buffer.asUint8List();
  }
}
