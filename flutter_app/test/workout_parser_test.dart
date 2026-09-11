import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/features/workout/workout_parser.dart';

import 'session_helpers.dart';

void main() {
  test('server targets use FTP precedence and Python ties to even', () {
    final p = workoutPayload();
    p['blocks'] = [
      {
        'type': 'ramp',
        'duration_sec': 10,
        'start_pct_ftp': .4,
        'start_watts': 300,
        'end_pct_ftp': .8,
        'target_cadence': 90,
      },
      {'type': 'steady', 'duration_sec': 10, 'target_watts': 150.0},
    ];
    final w = WorkoutParser.parse(p, ftp: 250);
    expect(w.blocks.first.targetAt(0), 100);
    expect(w.blocks.first.targetAt(5), 150);
    expect(w.blocks.first.targetAt(10), 200);
    expect(w.duration, 20);
    expect(w.blocks.last.start, 150);
  });
  test('strict invalid boundaries never reach trainer', () {
    final invalid = <Map<String, dynamic>>[
      {'type': 'steady', 'duration_sec': 0, 'target_watts': 100},
      {'type': 'steady', 'duration_sec': 1.5, 'target_watts': 100},
      {'type': 'steady', 'duration_sec': 1, 'target_watts': 100.5},
      {'type': 'steady', 'duration_sec': 1, 'target_watts': 32768},
      {'type': 'steady', 'duration_sec': 1, 'target_watts': true},
      {'type': 'steady', 'duration_sec': 1, 'target_pct_ftp': double.nan},
      {'type': 'steady', 'duration_sec': 1, 'target_pct_ftp': double.infinity},
      {'type': 'ramp', 'duration_sec': 10, 'start_watts': 100},
      {'type': 'steady', 'duration_sec': 86401, 'target_watts': 100},
      {
        'type': 'steady',
        'duration_sec': 1,
        'target_watts': 100,
        'target_cadence': 0,
      },
      {
        'type': 'steady',
        'duration_sec': 1,
        'target_watts': 100,
        'target_cadence': 90.0,
      },
    ];
    for (final b in invalid) {
      expect(
        () => WorkoutParser.parse({
          ...workoutPayload(),
          'blocks': [b],
        }, ftp: 250),
        throwsFormatException,
      );
    }
    for (final ftp in [0, 29, 2001]) {
      expect(
        () => WorkoutParser.parse(workoutPayload(), ftp: ftp),
        throwsFormatException,
      );
    }
    expect(
      () => WorkoutParser.parse({...workoutPayload(), 'blocks': []}, ftp: 250),
      throwsFormatException,
    );
    expect(
      () => WorkoutParser.parse({
        ...workoutPayload(),
        'blocks': List.filled(2001, {
          'type': 'steady',
          'duration_sec': 1,
          'target_watts': 100,
        }),
      }, ftp: 250),
      throwsFormatException,
    );
  });
}
