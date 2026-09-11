import 'package:cados_ftms_spike/features/trainer/ftms_protocol.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FTMS Indoor Bike Data', () {
    test('parses speed, cadence and signed power like Python reference', () {
      // Flags: instantaneous cadence and instantaneous power. Speed is present
      // when bit 0 is clear. Cadence has 0.5 rpm resolution.
      final result = FtmsProtocol.parseIndoorBikeData([
        0x44, 0x00,
        0x7b, 0x00, // speed
        0xb4, 0x00, // 90 rpm
        0xfa, 0x00, // 250 W
      ]);
      expect(result.cadenceRpm, 90);
      expect(result.powerWatts, 250);
    });

    test('keeps absent cadence and parses continuation power', () {
      final result = FtmsProtocol.parseIndoorBikeData([
        0x41, 0x00, // no speed, power present
        0x9c, 0xff, // -100 W signed
      ]);
      expect(result.cadenceRpm, isNull);
      expect(result.powerWatts, -100);
    });

    test('rejects truncated optional fields', () {
      expect(
        () => FtmsProtocol.parseIndoorBikeData([0x44, 0x00, 0x00]),
        throwsA(isA<FtmsProtocolException>()),
      );
    });
  });

  test('encodes FTMS commands byte-exactly', () {
    expect(FtmsProtocol.requestControl(), [0x00]);
    expect(FtmsProtocol.setTargetPower(200), [0x05, 0xc8, 0x00]);
    expect(FtmsProtocol.setTargetPower(-100), [0x05, 0x9c, 0xff]);
    expect(FtmsProtocol.start(), [0x07]);
    expect(FtmsProtocol.pause(), [0x08, 0x02]);
    expect(FtmsProtocol.stop(), [0x08, 0x01]);
  });

  test('parses control response and result', () {
    final response = FtmsProtocol.parseControlResponse([0x80, 0x05, 0x01]);
    expect(response, isNotNull);
    expect(response!.requestOpcode, 0x05);
    expect(response.successful, isTrue);
    expect(FtmsProtocol.parseControlResponse([0x01, 0x02]), isNull);
  });

  test('parses and applies supported power range', () {
    final range = FtmsProtocol.parsePowerRange([
      0x32, 0x00, // 50
      0xf4, 0x01, // 500
      0x05, 0x00, // 5
    ]);
    expect(range.minimumWatts, 50);
    expect(range.maximumWatts, 500);
    expect(range.clampAndRound(203), 205);
    expect(range.clampAndRound(900), 500);
  });

  test('reads target power capability from target feature bits', () {
    expect(FtmsProtocol.supportsTargetPower([0, 0, 0, 0, 8, 0, 0, 0]), isTrue);
    expect(FtmsProtocol.supportsTargetPower([0, 0, 0, 0, 0, 0, 0, 0]), isFalse);
    expect(FtmsProtocol.supportsTargetPower([0]), isTrue);
  });
}
