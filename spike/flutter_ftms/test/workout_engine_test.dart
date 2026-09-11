import 'package:flutter_test/flutter_test.dart';
import 'package:cados_ftms_spike/features/workout/workout.dart';
import 'package:cados_ftms_spike/features/workout/workout_engine.dart';

Workout fixture({int ftp = 250}) => Workout('Engine Test', const [
  WorkoutBlock(
    kind: BlockKind.ramp,
    label: 'Ramp',
    duration: 10,
    startPct: 0.4,
    endPct: 0.8,
    cadence: 85,
  ),
  WorkoutBlock(
    kind: BlockKind.steady,
    label: 'Steady',
    duration: 5,
    targetPct: 0.88,
    targetWatts: 260,
    cadence: 95,
  ),
], ftp: ftp);
void ride(
  WorkoutEngine e,
  double dt, {
  int watts = 200,
  bool connected = true,
}) => e.tick(dt, connected: connected, currentWatts: watts);
void main() {
  for (final row in <(int?, int?, int)>[
    (null, null, 200),
    (null, 240, 240),
    (0, 240, 240),
    (-1, 240, 200),
    (300, 240, 300),
  ]) {
    test(
      'Python FTP fallback $row',
      () => expect(
        Workout(
          'FTP',
          [
            const WorkoutBlock(
              kind: BlockKind.steady,
              label: 'steady',
              duration: 10,
              targetWatts: 100,
            ),
          ],
          ftp: row.$1,
          ftpReference: row.$2,
        ).ftpWatts,
        row.$3,
      ),
    );
  }
  test('Python zero ramp endpoint fallback and short workout final target', () {
    final block = const WorkoutBlock(
      kind: BlockKind.ramp,
      label: 'zero end',
      duration: 2,
      startWatts: 100,
      endWatts: 0,
    ).resolve(200);
    expect(block.targetAt(2), 100);
    final e = WorkoutEngine(
      Workout('short', [
        const WorkoutBlock(
          kind: BlockKind.steady,
          label: 's',
          duration: 2,
          targetWatts: 100,
        ),
      ]),
    );
    e.start();
    ride(e, .25);
    ride(e, 2);
    expect(e.state, WorkoutState.completed);
    expect(e.targetWatts, 58);
  });

  for (final row in [(200, 176), (250, 220), (300, 264)]) {
    test(
      'Python same_template_scales FTP ${row.$1}',
      () => expect(fixture(ftp: row.$1).blocks[1].start, row.$2),
    );
  }
  for (final row in [
    (0.0, 100),
    (2.5, 125),
    (5.0, 150),
    (10.0, 200),
    (12.0, 200),
    (-1.0, 100),
  ]) {
    test(
      'Python ramp interpolation ${row.$1}',
      () => expect(fixture().blocks[0].targetAt(row.$1), row.$2),
    );
  }
  test('Python ties to even and percent precedence', () {
    expect(pythonRound(2.5), 2);
    expect(pythonRound(3.5), 4);
    expect(pythonRound(-2.5), -2);
    expect(fixture().blocks[1].start, 220);
  });
  test('Python ramp_target_progresses_linearly after startup', () {
    final e = WorkoutEngine(fixture());
    e.start();
    ride(e, .25);
    expect(e.targetWatts, 30);
    ride(e, 5);
    expect(e.targetWatts, 150);
    expect(e.targetCadence, 85);
  });
  test('Python waiting, zero power auto pause and resume ramp', () {
    final e = WorkoutEngine(fixture());
    e.start();
    ride(e, 1, watts: 0);
    expect(e.state, WorkoutState.waitingForPedal);
    expect(e.elapsed, 0);
    ride(e, .25);
    ride(e, 1);
    ride(e, 1, watts: 0);
    ride(e, 1, watts: 0);
    expect(e.state, WorkoutState.paused);
    expect(e.autoPaused, true);
    final elapsed = e.elapsed;
    ride(e, 2, watts: 0);
    expect(e.elapsed, elapsed);
    ride(e, .25);
    expect(e.targetWatts, 30);
    expect(e.ramping, true);
  });
  test('Python manual pause and suspension require resume', () {
    final e = WorkoutEngine(fixture());
    e.start();
    ride(e, .25);
    ride(e, 1);
    e.pause();
    ride(e, 1);
    expect(e.state, WorkoutState.paused);
    e.resume();
    ride(e, .25);
    ride(e, 120);
    expect(e.state, WorkoutState.paused);
    expect(e.elapsed, 1);
    expect(e.autoPaused, false);
  });
  test('Python disconnect does not count time', () {
    final e = WorkoutEngine(fixture());
    e.start();
    ride(e, .25);
    ride(e, 1);
    ride(e, 1, connected: false);
    expect(e.elapsed, 1);
    expect(e.state, WorkoutState.paused);
    ride(e, .25);
    expect(e.state, WorkoutState.running);
    expect(e.elapsed, 1);
  });
  test('Python completion clamps last tick and cannot advance again', () {
    final e = WorkoutEngine(fixture());
    e.start();
    ride(e, .25);
    for (var i = 0; i < 4; i++) {
      ride(e, 3.7);
    }
    ride(e, 1);
    expect(e.elapsed, 15);
    expect(e.state, WorkoutState.completed);
    ride(e, 1);
    expect(e.elapsed, 15);
    e.start();
    expect(e.elapsed, 0);
  });
  test('block boundary smoothing and manual target clamping', () {
    final e = WorkoutEngine(fixture());
    e.start();
    ride(e, .25);
    ride(e, 5);
    ride(e, 5);
    expect(e.blockIndex, 1);
    expect(e.targetWatts, 150);
    ride(e, 1.5);
    expect(e.targetWatts, 185);
    ride(e, 1.5);
    expect(e.targetWatts, 220);
    e.adjustTarget(-500);
    expect(e.targetWatts, 0);
    e.adjustTarget(100000);
    expect(e.targetWatts, 32767);
    e.stop();
    final adjustment = e.adjustment;
    e.adjustTarget(1);
    expect(e.adjustment, adjustment);
  });
  test(
    'negative ticks clamp, invalid ticks reject and invalid workouts reject',
    () {
      final e = WorkoutEngine(fixture());
      e.start();
      ride(e, .25);
      ride(e, -1);
      expect(e.elapsed, 0);
      expect(() => ride(e, double.nan), throwsArgumentError);
      expect(() => Workout('empty', []), throwsArgumentError);
      expect(
        () => Workout('zero', [
          const WorkoutBlock(
            kind: BlockKind.steady,
            label: 'x',
            duration: 0,
            targetWatts: 100,
          ),
        ]),
        throwsArgumentError,
      );
    },
  );
}
