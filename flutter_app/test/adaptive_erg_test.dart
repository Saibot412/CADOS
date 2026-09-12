import 'package:cados_app/features/workout/workout.dart';
import 'package:cados_app/features/workout/workout_engine.dart';
import 'package:flutter_test/flutter_test.dart';

Workout adaptiveWorkout({
  String name = 'Adaptive',
  int watts = 300,
  int? cadence = 90,
  int duration = 60,
}) => Workout(name, [
  WorkoutBlock(
    kind: BlockKind.steady,
    label: 'Steady',
    duration: duration,
    targetWatts: watts,
    cadence: cadence,
  ),
]);

void ride(
  WorkoutEngine engine,
  double dt, {
  int watts = 200,
  double? cadence = 90,
  bool connected = true,
}) => engine.tick(
  dt,
  connected: connected,
  currentWatts: watts,
  currentCadence: cadence,
);

WorkoutEngine runningEngine({Workout? workout}) {
  final engine = WorkoutEngine(workout ?? adaptiveWorkout());
  engine.setAdaptiveErg(true);
  engine.start();
  ride(engine, 0.25);
  ride(engine, 5);
  return engine;
}

void main() {
  test('adaptive ERG triggers after 2s, relieves at 5W/s, and caps at 10%', () {
    final engine = runningEngine();

    ride(engine, 1, cadence: 75);
    expect(engine.adaptiveReliefWatts, 0);
    ride(engine, 1, cadence: 75);
    expect(engine.adaptiveReliefWatts, 5);
    expect(
      engine.targetWatts,
      300,
      reason: 'prescribed target stays transparent',
    );
    expect(engine.trainerTargetWatts, 295);

    for (var i = 0; i < 5; i++) {
      ride(engine, 1, cadence: 75);
    }
    expect(engine.adaptiveReliefWatts, 30);
    expect(engine.trainerTargetWatts, 270);
  });

  test('3rpm deadband does not trigger and relief recovers at 4W/s', () {
    final engine = runningEngine();
    for (var i = 0; i < 3; i++) {
      ride(engine, 1, cadence: 87);
    }
    expect(engine.adaptiveReliefWatts, 0);

    for (var i = 0; i < 4; i++) {
      ride(engine, 1, cadence: 75);
    }
    expect(engine.adaptiveReliefWatts, 15);

    ride(engine, 1, cadence: 87);
    expect(engine.adaptiveReliefWatts, 11);
    ride(engine, 1, cadence: 90);
    expect(engine.adaptiveReliefWatts, 7);
  });

  test('null and zero cadence never trigger and recover existing relief', () {
    final engine = runningEngine();
    for (var i = 0; i < 3; i++) {
      ride(engine, 1, cadence: 75);
    }
    expect(engine.adaptiveReliefWatts, 10);

    ride(engine, 1, cadence: null);
    expect(engine.adaptiveReliefWatts, 6);
    ride(engine, 1, cadence: 0);
    expect(engine.adaptiveReliefWatts, 2);
    ride(engine, 1, cadence: null);
    expect(engine.adaptiveReliefWatts, 0);

    ride(engine, 1, cadence: 75);
    expect(engine.adaptiveReliefWatts, 0);
  });

  test('disabled mode preserves exact target and toggling clears relief', () {
    final engine = runningEngine();
    for (var i = 0; i < 3; i++) {
      ride(engine, 1, cadence: 75);
    }
    expect(engine.adaptiveErgEnabled, isTrue);
    expect(engine.adaptiveReliefWatts, 10);

    engine.setAdaptiveErg(false);
    expect(engine.adaptiveErgEnabled, isFalse);
    expect(engine.adaptiveReliefWatts, 0);
    expect(engine.trainerTargetWatts, engine.targetWatts);

    for (var i = 0; i < 3; i++) {
      ride(engine, 1, cadence: 60);
    }
    expect(engine.trainerTargetWatts, engine.targetWatts);
  });

  test('block transition clears relief and restarts the trigger timer', () {
    final engine = runningEngine(
      workout: Workout('Blocks', const [
        WorkoutBlock(
          kind: BlockKind.steady,
          label: 'One',
          duration: 8,
          targetWatts: 300,
          cadence: 90,
        ),
        WorkoutBlock(
          kind: BlockKind.steady,
          label: 'Two',
          duration: 20,
          targetWatts: 300,
          cadence: 90,
        ),
      ]),
    );
    ride(engine, 1, cadence: 75);
    ride(engine, 1, cadence: 75);
    expect(engine.adaptiveReliefWatts, 5);

    ride(engine, 1, cadence: 75);
    expect(engine.blockIndex, 1);
    expect(engine.adaptiveReliefWatts, 0);
    ride(engine, 1, cadence: 75);
    expect(engine.adaptiveReliefWatts, 5);
  });

  test('pause, resume, disconnect, start, and stop reset adaptive state', () {
    final engine = runningEngine();
    ride(engine, 1, cadence: 75);
    engine.pause();
    engine.resume();
    ride(engine, 0.25);
    ride(engine, 1, cadence: 75);
    expect(engine.adaptiveReliefWatts, 0, reason: 'pause/resume resets timer');

    ride(engine, 1, cadence: 75);
    expect(engine.adaptiveReliefWatts, 5);
    ride(engine, 1, cadence: 75, connected: false);
    expect(engine.adaptiveReliefWatts, 0, reason: 'disconnect resets relief');

    ride(engine, 0.25);
    ride(engine, 1, cadence: 75);
    engine.stop();
    expect(engine.adaptiveReliefWatts, 0);
    engine.start();
    expect(engine.adaptiveReliefWatts, 0);
  });

  test('FTP ramps forcibly disable adaptive ERG', () {
    final engine = WorkoutEngine(adaptiveWorkout(name: 'FTP Ramp Test'));
    engine.setAdaptiveErg(true);
    expect(engine.adaptiveErgEnabled, isFalse);
    engine.start();
    ride(engine, 0.25);
    for (var i = 0; i < 3; i++) {
      ride(engine, 1, cadence: 60);
    }
    expect(engine.adaptiveReliefWatts, 0);
    expect(engine.trainerTargetWatts, engine.targetWatts);
  });

  test('effective target stays in trainer range without changing prescribed target', () {
    final high = runningEngine(workout: adaptiveWorkout(watts: 32767));
    for (var i = 0; i < 20; i++) {
      ride(high, 1, cadence: 1);
    }
    expect(high.targetWatts, 32767);
    expect(high.trainerTargetWatts, inInclusiveRange(0, 32767));

    final zero = runningEngine(workout: adaptiveWorkout(watts: 1));
    zero.adjustTarget(-100);
    for (var i = 0; i < 3; i++) {
      ride(zero, 1, cadence: 1);
    }
    expect(zero.targetWatts, 0);
    expect(zero.adaptiveReliefWatts, 0);
    expect(zero.trainerTargetWatts, 0);
  });
}
