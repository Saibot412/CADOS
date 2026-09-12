import 'dart:convert';

import 'package:cados_app/features/catalog/records.dart';
import 'package:cados_app/presentation/workout_editor.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show record;
import 'record_mutation_test.dart' show profile, signedIn;

const newId = '15b82c55-a517-4525-8c92-ebf94522760b';
const existingId = '18c43f02-5d32-41af-8366-18ae026f5956';

Map<String, dynamic> payload({String name = 'Threshold'}) => {
  'name': name,
  'description': 'Original',
  'future_metadata': {'kept': true},
  'blocks': [
    {
      'type': 'steady',
      'duration_sec': 300,
      'label': 'Work',
      'target_pct_ftp': 0.9,
      'target_watts': 222,
      'future_block': 7,
    },
  ],
};

Map<String, dynamic> workoutEnvelope({
  String id = existingId,
  String name = 'Threshold',
  int revision = 3,
  bool shared = false,
}) => {
  ...record(id, 'workout', payload(name: name), shared: shared),
  'revision': revision,
};

WorkoutRecord workout({bool shared = false}) =>
    WorkoutRecord(SyncRecord.fromJson(workoutEnvelope(shared: shared)));

Widget editorHarness(
  dynamic account, {
  WorkoutRecord? existing,
  bool copy = false,
  Size size = const Size(800, 900),
}) => MediaQuery(
  data: MediaQueryData(size: size),
  child: MaterialApp(
    home: WorkoutEditorPage(
      account: account,
      workout: existing,
      copy: copy,
      uuidGenerator: () => newId,
    ),
  ),
);

Finder keyedPrefix(String prefix) => find.byWidgetPredicate(
  (widget) =>
      widget.key is ValueKey<String> &&
      (widget.key! as ValueKey<String>).value.startsWith(prefix),
);

Future<void> tapInList(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.tap(finder);
}

void main() {
  testWidgets('adds, reorders, edits and removes blocks', (tester) async {
    final (account, _) = await signedIn();
    await tester.pumpWidget(editorHarness(account));

    expect(find.byKey(const Key('workoutBlock-0')), findsOneWidget);
    await tester.tap(find.byKey(const Key('addRampBlock')));
    await tester.pump();
    expect(find.byKey(const Key('workoutBlock-1')), findsOneWidget);
    expect(find.text('Start (W)'), findsOneWidget);

    await tester.tap(find.byKey(const Key('moveBlockUp-1')));
    await tester.pump();
    expect(find.text('Start (W)'), findsOneWidget);
    await tester.enterText(keyedPrefix('blockDuration-1'), '420');
    await tester.pump();
    expect(find.text('420'), findsOneWidget);

    await tester.drag(find.byType(ListView), const Offset(0, -350));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('removeBlock-1')));
    await tester.pump();
    expect(find.byKey(const Key('workoutBlock-1')), findsNothing);
  });

  testWidgets('creates revision zero and waits for authoritative refresh', (
    tester,
  ) async {
    final (account, http) = await signedIn();
    final created = workoutEnvelope(
      id: newId,
      name: 'Morning Ride',
      revision: 1,
    );
    http.json({
      'records': [created],
    });
    http.json({
      'records': [profile(), created],
    });
    await tester.pumpWidget(editorHarness(account));

    await tester.enterText(
      find.byKey(const Key('workoutName')),
      'Morning Ride',
    );
    await tapInList(tester, find.byKey(const Key('saveWorkout')));
    await tester.pumpAndSettle();

    expect(find.text('Workout wurde vom Server angelegt.'), findsOneWidget);
    final body = jsonDecode(http.requests[2].body!) as Map<String, dynamic>;
    final change = (body['changes'] as List).single as Map<String, dynamic>;
    expect(change['id'], newId);
    expect(change['kind'], 'workout');
    expect(change['revision'], 0);
    expect(change['shared'], isFalse);

    final revised = workoutEnvelope(
      id: newId,
      name: 'Morning Ride 2',
      revision: 2,
    );
    http.json({
      'records': [revised],
    });
    http.json({
      'records': [profile(), revised],
    });
    await tester.scrollUntilVisible(
      find.byKey(const Key('workoutName')),
      -300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(
      find.byKey(const Key('workoutName')),
      'Morning Ride 2',
    );
    await tapInList(tester, find.byKey(const Key('saveWorkout')));
    await tester.pumpAndSettle();
    final secondBody =
        jsonDecode(http.requests[4].body!) as Map<String, dynamic>;
    final secondChange =
        (secondBody['changes'] as List).single as Map<String, dynamic>;
    expect(secondChange['id'], newId);
    expect(secondChange['revision'], 1);
    expect(
      (secondChange['payload'] as Map<String, dynamic>)['future_metadata'],
      {'kept': true},
    );
  });

  testWidgets('private edit keeps metadata and uses current revision', (
    tester,
  ) async {
    final (account, http) = await signedIn();
    final updated = workoutEnvelope(name: 'Updated', revision: 4);
    http.json({
      'records': [updated],
    });
    http.json({
      'records': [profile(), updated],
    });
    await tester.pumpWidget(editorHarness(account, existing: workout()));

    await tester.enterText(find.byKey(const Key('workoutName')), 'Updated');
    await tapInList(tester, find.byKey(const Key('saveWorkout')));
    await tester.pumpAndSettle();

    final body = jsonDecode(http.requests[2].body!) as Map<String, dynamic>;
    final change = (body['changes'] as List).single as Map<String, dynamic>;
    final saved = change['payload'] as Map<String, dynamic>;
    expect(change['id'], existingId);
    expect(change['revision'], 3);
    expect(saved['future_metadata'], {'kept': true});
    expect((saved['blocks'] as List).single['future_block'], 7);
    expect((saved['blocks'] as List).single['target_watts'], 222);
  });

  testWidgets('shared workout can only create a private copy', (tester) async {
    final (account, http) = await signedIn();
    final copied = workoutEnvelope(
      id: newId,
      name: 'Threshold (Kopie)',
      revision: 1,
    );
    http.json({
      'records': [copied],
    });
    http.json({
      'records': [profile(), copied],
    });
    await tester.pumpWidget(
      editorHarness(account, existing: workout(shared: true)),
    );

    expect(find.text('Geteiltes Workout ist schreibgeschützt'), findsOneWidget);
    await tapInList(tester, find.byKey(const Key('saveWorkout')));
    await tester.pumpAndSettle();

    final body = jsonDecode(http.requests[2].body!) as Map<String, dynamic>;
    final change = (body['changes'] as List).single as Map<String, dynamic>;
    expect(change['id'], newId);
    expect(change['revision'], 0);
    expect(change['shared'], isFalse);
  });

  testWidgets('invalid draft is rejected before network access', (
    tester,
  ) async {
    final (account, http) = await signedIn();
    await tester.pumpWidget(editorHarness(account));
    final before = http.requests.length;

    await tester.tap(find.byKey(const Key('removeBlock-0')));
    await tester.pump();
    await tapInList(tester, find.byKey(const Key('saveWorkout')));
    await tester.pump();

    expect(find.byKey(const Key('workoutError')), findsOneWidget);
    expect(find.textContaining('1 bis 2000'), findsOneWidget);
    expect(http.requests, hasLength(before));
  });

  testWidgets('dirty back navigation requires explicit discard', (
    tester,
  ) async {
    final (account, _) = await signedIn();
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute<void>(
                  builder: (_) => WorkoutEditorPage(
                    account: account,
                    uuidGenerator: () => newId,
                  ),
                ),
              ),
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('workoutName')), 'Changed');
    await tester.pump();
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    expect(find.text('Änderungen verwerfen?'), findsOneWidget);
    await tester.tap(find.text('Weiter bearbeiten'));
    await tester.pumpAndSettle();
    expect(find.byType(WorkoutEditorPage), findsOneWidget);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    await tester.tap(find.text('Verwerfen'));
    await tester.pumpAndSettle();
    expect(find.text('Open'), findsOneWidget);
  });

  testWidgets('wide layout renders real preview semantics', (tester) async {
    final (account, _) = await signedIn();
    await tester.binding.setSurfaceSize(const Size(1200, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      editorHarness(account, existing: workout(), size: const Size(1200, 800)),
    );
    expect(
      find.bySemanticsLabel('Leistungsverlauf mit 1 Blöcken und 300 Sekunden'),
      findsOneWidget,
    );
    expect(find.text('Vorschau'), findsOneWidget);
  });
}
