import 'dart:convert';

import 'package:cados_app/features/catalog/record_mutation_controller.dart';
import 'package:cados_app/features/catalog/records.dart';
import 'package:cados_app/presentation/plan_editor.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'calendar_page_test.dart'
    show
        completedSession,
        harness,
        planReadyId,
        planRecord,
        signedInCalendar,
        workoutId,
        workoutRecord;
import 'record_mutation_test.dart' show profile;

Widget editorLauncher({
  required dynamic account,
  PlanRecord? plan,
  Future<DateTime?> Function(BuildContext, DateTime)? pickDate,
  String newId = '71b47a09-201c-452f-b049-9211e8a7486d',
}) => MaterialApp(
  home: Builder(
    builder: (context) => Scaffold(
      body: Center(
        child: FilledButton(
          key: const Key('openEditor'),
          onPressed: () => Navigator.push<void>(
            context,
            MaterialPageRoute(
              builder: (_) => PlanEditorPage(
                account: account,
                initialDate: '2026-04-01',
                plan: plan,
                uuidGenerator: () => newId,
                pickDate: pickDate,
              ),
            ),
          ),
          child: const Text('Open'),
        ),
      ),
    ),
  ),
);

void main() {
  testWidgets(
    'new planning uses UUID revision zero and authoritative refresh',
    (tester) async {
      const newId = '71b47a09-201c-452f-b049-9211e8a7486d';
      final (account, http) = await signedInCalendar();
      final created = planRecord(
        newId,
        workoutId,
        'Tempo',
        revision: 1,
        date: '2026-04-02',
      );
      http.json({
        'records': [created],
      });
      http.json({
        'records': [profile(), workoutRecord(), created],
      });
      await tester.pumpWidget(
        editorLauncher(
          account: account,
          pickDate: (_, _) async => DateTime(2026, 4, 2, 23, 55),
        ),
      );
      await tester.tap(find.byKey(const Key('openEditor')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('planDate')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('planWorkout')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tempo').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('savePlan')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('openEditor')), findsOneWidget);
      expect(
        account.catalog!.upcoming(DateTime(2026, 4, 2)).single.record.id,
        newId,
      );
      final body = jsonDecode(http.requests[2].body!) as Map<String, dynamic>;
      expect(body['changes'], [
        {
          'id': newId,
          'kind': 'plan',
          'revision': 0,
          'deleted': false,
          'shared': false,
          'payload': {
            'date': '2026-04-02',
            'workout_id': workoutId,
            'workout_name': 'Tempo',
          },
        },
      ]);
    },
  );

  testWidgets(
    'moving a plan uses current revision and preserves unknown fields',
    (tester) async {
      final (account, http) = await signedInCalendar();
      final current = account.catalog!
          .upcoming(DateTime(2026, 4, 1))
          .firstWhere((plan) => plan.record.id == planReadyId);
      final moved = planRecord(
        planReadyId,
        workoutId,
        'Tempo',
        revision: 4,
        date: '2026-04-03',
      );
      http.json({
        'records': [moved],
      });
      http.json({
        'records': [profile(), workoutRecord(), moved],
      });
      await tester.pumpWidget(
        editorLauncher(
          account: account,
          plan: current,
          pickDate: (_, _) async => DateTime(2026, 4, 3),
        ),
      );
      await tester.tap(find.byKey(const Key('openEditor')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('planDate')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('savePlan')));
      await tester.pumpAndSettle();

      final change =
          (jsonDecode(http.requests[2].body!)['changes'] as List).single;
      expect(change['revision'], 3);
      expect(change['payload']['date'], '2026-04-03');
      expect(change['payload']['future'], {'kept': true});
      expect(
        account.catalog!.upcoming(DateTime(2026, 4, 3)).single.date,
        '2026-04-03',
      );
    },
  );

  test('refreshed payload must match the acknowledged plan', () async {
    final (account, http) = await signedInCalendar();
    final current = account.catalog!
        .upcoming(DateTime(2026, 4, 1))
        .firstWhere((plan) => plan.record.id == planReadyId);
    final acknowledged = planRecord(
      planReadyId,
      workoutId,
      'Tempo',
      revision: 4,
      date: '2026-04-02',
    );
    final mismatchedRefresh = planRecord(
      planReadyId,
      workoutId,
      'Tempo',
      revision: 4,
      date: '2026-04-03',
    );
    http.json({
      'records': [acknowledged],
    });
    http.json({
      'records': [profile(), workoutRecord(), mismatchedRefresh],
    });
    final mutation = RecordMutationController(account);

    expect(
      await mutation.update(current.record, {
        ...current.record.payload,
        'date': '2026-04-02',
      }),
      isFalse,
    );
    expect(mutation.saved, isFalse);
    expect(mutation.error, isNotNull);
  });

  testWidgets('server-valid legacy dates open inside date picker bounds', (
    tester,
  ) async {
    final (account, _) = await signedInCalendar();
    final legacy = PlanRecord(
      SyncRecord.fromJson(
        planRecord(
          planReadyId.toUpperCase(),
          workoutId.toUpperCase(),
          'Tempo',
          date: '0999-01-01',
        ),
      ),
    );
    await tester.pumpWidget(editorLauncher(account: account, plan: legacy));
    await tester.tap(find.byKey(const Key('openEditor')));
    await tester.pumpAndSettle();
    expect(
      find.text(
        'Das bisherige Workout ist nicht mehr verfügbar. Bitte ein anderes auswählen.',
      ),
      findsNothing,
    );
    await tester.tap(find.byKey(const Key('planDate')));
    await tester.pumpAndSettle();

    expect(find.byType(DatePickerDialog), findsOneWidget);
  });

  for (final scenario in [
    (status: 401, label: '401'),
    (status: 409, label: '409'),
    (status: 500, label: '500'),
  ]) {
    test(
      'plan mutation ${scenario.label} is visible and never saved',
      () async {
        final (account, http) = await signedInCalendar();
        final current = account.catalog!
            .upcoming(DateTime(2026, 4, 1))
            .firstWhere((plan) => plan.record.id == planReadyId);
        final mutation = RecordMutationController(account);
        http.json({'detail': 'rejected'}, scenario.status);

        expect(
          await mutation.update(current.record, {
            ...current.record.payload,
            'date': '2026-04-02',
          }),
          isFalse,
        );
        expect(mutation.saved, isFalse);
        expect(mutation.error, isNotNull);
        if (scenario.status == 409) expect(mutation.error, contains('409'));
        expect(
          account.catalog?.records.any((record) => record.id == planReadyId) ??
              false,
          scenario.status == 401 ? isFalse : isTrue,
        );
      },
    );
  }

  test('offline plan mutation is blocked without optimistic state', () async {
    final (account, _) = await signedInCalendar();
    final current = account.catalog!
        .upcoming(DateTime(2026, 4, 1))
        .firstWhere((plan) => plan.record.id == planReadyId);
    final mutation = RecordMutationController(account);

    expect(
      await mutation.update(current.record, {
        ...current.record.payload,
        'date': '2026-04-02',
      }),
      isFalse,
    );
    expect(mutation.saved, isFalse);
    expect(mutation.error, isNotNull);
    expect(
      account.catalog!
          .upcoming(DateTime(2026, 4, 1))
          .any((p) => p.record.id == planReadyId),
      isTrue,
    );
  });

  test('stale catalog generation blocks a plan before another POST', () async {
    final (account, http) = await signedInCalendar();
    final current = account.catalog!
        .upcoming(DateTime(2026, 4, 1))
        .firstWhere((plan) => plan.record.id == planReadyId);
    final mutation = RecordMutationController(account);
    http.json({
      'id': 'account',
      'email': 'rider@example.invalid',
      'admin': false,
      'active': true,
    });
    http.json({
      'records': account.catalog!.records
          .map((record) => record.toJson())
          .toList(),
    });
    await account.refresh();
    final before = http.requests.length;

    expect(
      await mutation.update(current.record, {
        ...current.record.payload,
        'date': '2026-04-02',
      }),
      isFalse,
    );
    expect(mutation.saved, isFalse);
    expect(mutation.error, contains('409'));
    expect(http.requests.length, before);
  });

  testWidgets('removing a plan can be cancelled without a request', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, http) = await signedInCalendar();
    await tester.pumpWidget(
      harness(account, onSelect: (_, _) {}, size: const Size(1200, 900)),
    );
    final before = http.requests.length;

    await tester.tap(find.byKey(const Key('deletePlan-$planReadyId')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Abbrechen'));
    await tester.pumpAndSettle();

    expect(http.requests.length, before);
    expect(find.byKey(const Key('calendarPlan-$planReadyId')), findsOneWidget);
  });

  testWidgets('removing a plan confirms and sends current revision tombstone', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, http) = await signedInCalendar();
    final tombstone = planRecord(
      planReadyId,
      workoutId,
      'Tempo',
      revision: 4,
      deleted: true,
    );
    http.json({
      'records': [tombstone],
    });
    http.json({
      'records': [profile(), workoutRecord(), completedSession()],
    });
    await tester.pumpWidget(
      harness(account, onSelect: (_, _) {}, size: const Size(1200, 900)),
    );
    await tester.tap(find.byKey(const Key('deletePlan-$planReadyId')));
    await tester.pumpAndSettle();
    expect(find.text('Planung entfernen?'), findsOneWidget);
    await tester.tap(find.text('Entfernen'));
    await tester.pumpAndSettle();

    final change =
        (jsonDecode(http.requests[2].body!)['changes'] as List).single;
    expect(change['id'], planReadyId);
    expect(change['revision'], 3);
    expect(change['deleted'], isTrue);
    expect(find.byKey(const Key('calendarPlan-$planReadyId')), findsNothing);
  });
}
