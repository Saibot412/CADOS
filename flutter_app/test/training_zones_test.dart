import 'package:cados_app/features/profile/training_zones.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('power zones reproduce Python half-up contiguous FTP bounds', () {
    final zones = powerZones(200);
    expect(zones.map((zone) => zone.rangeLabel), [
      '0-110 W',
      '111-150 W',
      '151-180 W',
      '181-210 W',
      '211-240 W',
      '241-300 W',
      '301+ W',
    ]);
    expect(zones.map((zone) => zone.percentLabel), [
      '0-55% FTP',
      '56-75% FTP',
      '76-90% FTP',
      '91-105% FTP',
      '106-120% FTP',
      '121-150% FTP',
      '151%+ FTP',
    ]);
    expect(powerZoneForWatts(150, 250).label, 'Z2 Endurance');
    expect(powerZoneForWatts(225, 250).label, 'Z3 Tempo');
    expect(powerZoneForWatts(320, 250).label, 'Z6 Anaerobic');
    expect(powerZoneForWatts(150.1, 200).code, 'Z3');
    expect(powerZoneForWatts(149.9, 200).code, 'Z2');
  });

  test('power boundaries are gap-free and use half-up rounding', () {
    final zones = powerZones(250);
    expect(zones.first.upper, 138); // 137.5 rounds upward like Python.
    for (var index = 1; index < zones.length; index++) {
      expect(zones[index].lower, zones[index - 1].upper! + 1);
    }
    expect(powerZoneForWatts(-10, 250), zones.first);
    expect(powerZoneForWatts(10000, 250), zones.last);
  });

  test('heart-rate zones are deterministic and contiguous from max HR', () {
    final zones = heartRateZones(190);
    expect(zones.map((zone) => zone.rangeLabel), [
      '0-114 bpm',
      '115-133 bpm',
      '134-152 bpm',
      '153-171 bpm',
      '172+ bpm',
    ]);
    expect(zones.map((zone) => zone.percentLabel), [
      '0-60% HFmax',
      '61-70% HFmax',
      '71-80% HFmax',
      '81-90% HFmax',
      '91%+ HFmax',
    ]);
    expect(heartRateZoneForBpm(152, 190).code, 'H3');
    expect(heartRateZoneForBpm(190, 190).code, 'H5');
  });

  test('invalid physiological anchors are rejected', () {
    for (final ftp in [0, -1]) {
      expect(() => powerZones(ftp), throwsArgumentError);
    }
    for (final maxHr in [0, -1]) {
      expect(() => heartRateZones(maxHr), throwsArgumentError);
    }
  });
}
