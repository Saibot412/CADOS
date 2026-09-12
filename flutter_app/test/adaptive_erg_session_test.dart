import 'package:cados_app/features/catalog/records.dart';
import 'package:cados_app/features/session/workout_session_controller.dart';
import 'package:cados_app/features/workout/workout_engine.dart';
import 'package:cados_app/presentation/training_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show record;
import 'session_helpers.dart';

Future<void> reachSteadyTarget(
  SessionHarness harness, {
  double? cadence = 90,
}) async {
  await harness.session.start();
  await harness.step(cadence: cadence);
  for (var i = 0; i < 5; i++) {
    await harness.step(cadence: cadence);
  }
}

void main() {
  late SessionHarness harness;
  var harnessClosed = false;
  tearDown(() async {
    if (!harnessClosed) await harness.close();
    harnessClosed = false;
  });

  test(
    'stored opt-in sends only confirmed adaptive effective targets',
    () async {
      harness = SessionHarness(
        trainingPreferences: MemoryTrainingPreferences(true),
      );
      await harness.prepare(duration: 40);
      await reachSteadyTarget(harness);
      expect(harness.session.adaptiveErgPreferred, isTrue);
      expect(harness.session.adaptiveErgActive, isTrue);
      expect(harness.session.prescribedTarget, 200);

      await harness.step(cadence: 70);
      await harness.step(cadence: 70);
      await harness.step(cadence: 70);

      expect(harness.session.adaptiveReliefWatts, 10);
      expect(harness.session.prescribedTarget, 200);
      expect(harness.session.effectiveTrainerTarget, 190);
      expect(harness.transport.sentPower.last, 190);
      final adaptiveLogs = harness.logger.lines
          .where((line) => line.startsWith('Adaptive ERG'))
          .toList();
      expect(adaptiveLogs, isNotEmpty);
      expect(adaptiveLogs.join(), isNot(contains('rider')));
      expect(adaptiveLogs.join(), isNot(contains('Server workout')));
    },
  );

  test(
    'preference write failure never enables adaptive ERG optimistically',
    () async {
      final preferences = MemoryTrainingPreferences()..fail = true;
      harness = SessionHarness(trainingPreferences: preferences);
      await harness.prepare(duration: 40);

      await harness.session.setAdaptiveErg(true);

      expect(harness.session.adaptiveErgPreferred, isFalse);
      expect(harness.session.adaptiveErgActive, isFalse);
      expect(harness.session.error, isNotNull);
      expect(preferences.writes, isEmpty);
    },
  );

  test(
    'missing cadence does not trigger relief and disabling restores target',
    () async {
      harness = SessionHarness(
        trainingPreferences: MemoryTrainingPreferences(true),
      );
      await harness.prepare(duration: 40);
      await reachSteadyTarget(harness);
      for (var i = 0; i < 3; i++) {
        await harness.step(cadence: 70);
      }
      expect(harness.session.adaptiveReliefWatts, 10);

      await harness.step(cadence: null);
      expect(harness.session.adaptiveReliefWatts, 5);
      await harness.session.setAdaptiveErg(false);

      expect(harness.trainingPreferences.writes, [false]);
      expect(harness.session.adaptiveErgActive, isFalse);
      expect(harness.session.adaptiveReliefWatts, 0);
      expect(harness.session.effectiveTrainerTarget, 200);
      expect(harness.transport.sentPower.last, 200);
    },
  );

  test('rejected adaptive target pauses and never becomes effective', () async {
    harness = SessionHarness(
      trainingPreferences: MemoryTrainingPreferences(true),
    );
    await harness.prepare(duration: 40);
    await reachSteadyTarget(harness);
    final confirmed = harness.session.effectiveTrainerTarget;
    await harness.step(cadence: 70);
    harness.transport.failPower = true;
    await harness.step(cadence: 70);

    expect(harness.session.state, WorkoutState.paused);
    expect(harness.session.effectiveTrainerTarget, confirmed);
    expect(harness.session.adaptiveReliefWatts, 0);
    expect(harness.session.error, isNotNull);
  });

  testWidgets('FTP ramp visibly disables adaptive ERG despite stored opt-in', (
    tester,
  ) async {
    harness = SessionHarness(
      trainingPreferences: MemoryTrainingPreferences(true),
    );
    await harness.prepare(duration: 40);
    final profile = harness.account.catalog!.profiles.single.record;
    final ftpWorkout = record(
      '165adcb9-77e1-46c3-809b-2c4d2ea50446',
      'workout',
      {
        'name': 'FTP Ramp Test (ERG)',
        'source_name': 'ftp-ramp.json',
        'blocks': [
          {
            'type': 'steady',
            'label': 'Step 1',
            'duration_sec': 60,
            'target_watts': 300,
            'target_cadence': 90,
          },
        ],
      },
    );
    harness.account.catalog = Catalog.fromJson({
      'records': [profile.toJson(), ftpWorkout],
    });
    final workout = harness.account.catalog!.workouts.single;
    expect(harness.session.select(workout), isTrue);
    await harness.session.start();

    expect(harness.session.adaptiveErgPreferred, isTrue);
    expect(harness.session.adaptiveErgAllowed, isFalse);
    expect(harness.session.adaptiveErgActive, isFalse);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TrainingScreen(session: harness.session, sync: harness.sync),
        ),
      ),
    );
    await tester.pump();
    final toggle = tester.widget<SwitchListTile>(
      find.byKey(const Key('adaptiveErgToggle')),
    );
    expect(toggle.onChanged, isNull);
    expect(toggle.value, isFalse);
    expect(find.textContaining('FTP-Rampentests'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    // Widget tests use a fake async zone; the stream-backed harness is detached
    // here and is covered by the non-widget shutdown tests.
    harnessClosed = true;
  });
}
