import 'package:flutter_test/flutter_test.dart';
import 'package:cados_ftms_spike/features/heart_rate/heart_rate.dart';

void main() {
  for (final sample in <(List<int>, int)>[
    ([0, 72], 72),
    ([1, 44, 1], 300),
    ([30, 150, 255, 255, 0], 150),
    ([31, 0, 1, 255], 256),
  ]) {
    test(
      'HR flags ${sample.$1}',
      () => expect(HeartRateMeasurement.parse(sample.$1).bpm, sample.$2),
    );
  }
  for (final bytes in <List<int>>[
    [],
    [0],
    [1],
    [1, 4],
  ]) {
    test(
      'truncated $bytes',
      () => expect(
        () => HeartRateMeasurement.parse(bytes),
        throwsFormatException,
      ),
    );
  }
}
