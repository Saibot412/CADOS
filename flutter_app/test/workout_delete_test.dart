import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/presentation/catalog_pages.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show TestHttp, TestStore, record, testUser;
import 'record_mutation_test.dart' show profile;

const workoutId = '15b82c55-a517-4525-8c92-ebf94522760b';
const sessionId = 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d';

Map<String, dynamic> workout({
  int revision = 3,
  bool deleted = false,
  bool shared = false,
}) => {
  ...record(
    workoutId,
    'workout',
    {
      'name': 'Private Workout',
      'blocks': [
        {'type': 'steady', 'duration_sec': 300, 'target_watts': 180},
      ],
    },
    deleted: deleted,
    shared: shared,
  ),
  'revision': revision,
};

Map<String, dynamic> historicalSession() => record(sessionId, 'session', {
  'status': 'completed',
  'workout_name': 'Private Workout',
  'timestamp': '2026-09-12T08:00:00Z',
  'duration_sec': 300,
});

Future<(AccountController, TestHttp)> signedInWithWorkout({
  bool shared = false,
}) async {
  final http = TestHttp(), store = TestStore();
  final account = AccountController(http, store, store);
  http.json({'token': 'test-only-token', 'user': testUser});
  http.json({
    'records': [profile(), workout(shared: shared), historicalSession()],
  });
  await account.login('rider@example.invalid', 'test-only-password');
  return (account, http);
}

Widget catalogHarness(AccountController account) => MaterialApp(
  home: Scaffold(
    body: AnimatedBuilder(
      animation: account,
      builder: (context, _) =>
          CatalogPage(account: account, workouts: true, onSelect: (_, _) {}),
    ),
  ),
);

void main() {
  testWidgets('delete requires confirmation and cancel sends nothing', (
    tester,
  ) async {
    final (account, http) = await signedInWithWorkout();
    await tester.pumpWidget(catalogHarness(account));
    final requestsBefore = http.requests.length;

    await tester.tap(find.byKey(const Key('deleteWorkout-$workoutId')));
    await tester.pumpAndSettle();
    expect(find.text('Workout löschen?'), findsOneWidget);
    expect(find.textContaining('Trainings bleiben erhalten'), findsOneWidget);
    await tester.tap(find.text('Abbrechen'));
    await tester.pumpAndSettle();

    expect(http.requests, hasLength(requestsBefore));
    expect(find.text('Private Workout'), findsOneWidget);
  });

  testWidgets('confirmed delete sends tombstone and keeps history', (
    tester,
  ) async {
    final (account, http) = await signedInWithWorkout();
    final tombstone = workout(revision: 4, deleted: true);
    http.json({
      'records': [tombstone],
    });
    http.json({
      'records': [profile(), tombstone, historicalSession()],
    });
    await tester.pumpWidget(catalogHarness(account));

    await tester.tap(find.byKey(const Key('deleteWorkout-$workoutId')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Workout löschen'));
    await tester.pumpAndSettle();

    expect(find.text('Workout wurde gelöscht.'), findsOneWidget);
    expect(account.catalog!.workouts, isEmpty);
    expect(account.catalog!.sessions.single.workoutName, 'Private Workout');
    expect(http.requests[2].body, contains('"deleted":true'));
    expect(http.requests[2].body, contains('"revision":3'));
  });

  testWidgets('delete conflict keeps workout and explains refresh', (
    tester,
  ) async {
    final (account, http) = await signedInWithWorkout();
    http.json({}, 409);
    await tester.pumpWidget(catalogHarness(account));

    await tester.tap(find.byKey(const Key('deleteWorkout-$workoutId')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Workout löschen'));
    await tester.pumpAndSettle();

    expect(find.textContaining('neu laden'), findsOneWidget);
    expect(account.catalog!.workouts.single.name, 'Private Workout');
  });

  testWidgets('shared workout is read-only and cannot be deleted', (
    tester,
  ) async {
    final (account, _) = await signedInWithWorkout(shared: true);
    await tester.pumpWidget(catalogHarness(account));
    expect(find.byKey(const Key('deleteWorkout-$workoutId')), findsNothing);
    expect(find.byIcon(Icons.lock_outline), findsOneWidget);
  });
}
