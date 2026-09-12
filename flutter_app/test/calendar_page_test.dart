import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/features/catalog/records.dart';
import 'package:cados_app/presentation/calendar_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show TestHttp, TestStore, record, testUser;
import 'record_mutation_test.dart' show profile;

const workoutId = '15b82c55-a517-4525-8c92-ebf94522760b';
const missingWorkoutId = '83693006-745d-4469-8704-25ce40f49464';
const planReadyId = 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d';
const planMissingId = '513d61eb-7a0f-4aaa-b231-523c92db3d3a';
const planDoneId = 'f972d39e-6588-46fa-83fa-4a759f1407fd';
const planPastId = '864026b1-33b1-4a93-ad11-441435912ed8';
const sessionId = 'ad605aa7-6daa-465e-9f06-f287566c03ad';

Map<String, dynamic> workoutRecord() => record(workoutId, 'workout', {
  'name': 'Tempo',
  'blocks': [
    {'type': 'steady', 'duration_sec': 600, 'target_watts': 180},
  ],
});

Map<String, dynamic> planRecord(
  String id,
  String workoutId,
  String name, {
  String date = '2026-04-01',
  int revision = 3,
  bool deleted = false,
}) => {
  ...record(id, 'plan', {
    'date': date,
    'workout_id': workoutId,
    'workout_name': name,
    'future': {'kept': true},
  }, deleted: deleted),
  'revision': revision,
};

Map<String, dynamic> completedSession() => record(sessionId, 'session', {
  'plan_id': planDoneId,
  'status': 'completed',
  'workout_name': 'Tempo erledigt',
  'timestamp': '2026-04-01T19:00:00Z',
  'duration_sec': 600,
});

Future<(AccountController, TestHttp)> signedInCalendar() async {
  final http = TestHttp(), store = TestStore();
  final account = AccountController(http, store, store);
  http.json({'token': 'test-only-token', 'user': testUser});
  http.json({
    'records': [
      profile(),
      workoutRecord(),
      planRecord(planReadyId, workoutId, 'Tempo'),
      planRecord(planMissingId, missingWorkoutId, 'Gelöschtes Workout'),
      planRecord(planDoneId, workoutId, 'Tempo erledigt'),
      planRecord(
        planPastId,
        workoutId,
        'Vergangenes Training',
        date: '2026-03-31',
      ),
      completedSession(),
    ],
  });
  await account.login('rider@example.invalid', 'test-only-password');
  return (account, http);
}

Widget harness(
  AccountController account, {
  required void Function(WorkoutRecord, String) onSelect,
  Size size = const Size(430, 900),
}) => MediaQuery(
  data: MediaQueryData(size: size),
  child: MaterialApp(
    home: Scaffold(
      body: AnimatedBuilder(
        animation: account,
        builder: (context, _) => CalendarPage(
          account: account,
          now: () => DateTime(2026, 4, 1, 0, 30),
          onSelect: onSelect,
        ),
      ),
    ),
  ),
);

void main() {
  for (final size in [const Size(430, 900), const Size(1200, 900)]) {
    testWidgets('calendar renders local day and plans at $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final (account, _) = await signedInCalendar();
      await tester.pumpWidget(
        harness(account, onSelect: (_, _) {}, size: size),
      );

      expect(find.text('April 2026'), findsOneWidget);
      expect(find.byKey(const Key('calendarDay-2026-04-01')), findsOneWidget);
      expect(find.byKey(const Key('calendarCount-2026-04-01')), findsOneWidget);
      expect(find.text('2026-04-01'), findsOneWidget);
      expect(find.text('Tempo'), findsOneWidget);
    });
  }

  testWidgets('startable, missing and completed plans are distinguished', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, _) = await signedInCalendar();
    WorkoutRecord? selectedWorkout;
    String? selectedPlan;
    await tester.pumpWidget(
      harness(
        account,
        onSelect: (workout, plan) {
          selectedWorkout = workout;
          selectedPlan = plan;
        },
        size: const Size(1200, 900),
      ),
    );

    expect(find.text('Workout nicht mehr verfügbar'), findsOneWidget);
    expect(find.text('Abgeschlossen'), findsOneWidget);
    final missingButton = tester.widget<FilledButton>(
      find.byKey(const Key('startPlan-$planMissingId')),
    );
    final doneButton = tester.widget<FilledButton>(
      find.byKey(const Key('startPlan-$planDoneId')),
    );
    expect(missingButton.onPressed, isNull);
    expect(doneButton.onPressed, isNull);

    await tester.tap(find.byKey(const Key('startPlan-$planReadyId')));
    expect(selectedWorkout?.record.id, workoutId);
    expect(selectedPlan, planReadyId);
  });

  testWidgets('month navigation keeps the selected local day component', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, _) = await signedInCalendar();
    await tester.pumpWidget(
      harness(account, onSelect: (_, _) {}, size: const Size(1200, 900)),
    );

    await tester.tap(find.byKey(const Key('nextMonth')));
    await tester.pump();
    expect(find.text('Mai 2026'), findsOneWidget);
    expect(find.text('2026-05-01'), findsOneWidget);
    await tester.tap(find.byKey(const Key('previousMonth')));
    await tester.pump();
    expect(find.text('April 2026'), findsOneWidget);
  });

  testWidgets('past plans are visible but cannot redirect into training', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, _) = await signedInCalendar();
    var selected = false;
    await tester.pumpWidget(
      harness(
        account,
        onSelect: (_, _) => selected = true,
        size: const Size(1200, 900),
      ),
    );
    await tester.tap(find.byKey(const Key('previousMonth')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('calendarDay-2026-03-31')));
    await tester.pump();

    expect(find.text('Datum liegt in der Vergangenheit'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('startPlan-$planPastId')),
    );
    expect(button.onPressed, isNull);
    expect(selected, isFalse);
  });

  testWidgets('training history remains accessible from the calendar', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, _) = await signedInCalendar();
    await tester.pumpWidget(
      harness(account, onSelect: (_, _) {}, size: const Size(1200, 900)),
    );

    final history = find.byKey(const Key('calendarSession-$sessionId'));
    await tester.ensureVisible(history);
    await tester.tap(history);
    await tester.pumpAndSettle();
    expect(find.text('Trainingsergebnis'), findsOneWidget);
  });
}
