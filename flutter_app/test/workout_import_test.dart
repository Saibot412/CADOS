import 'dart:convert';

import 'package:cados_app/features/workout/workout_import.dart';
import 'package:cados_app/presentation/catalog_pages.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show record;
import 'record_mutation_test.dart' show profile, signedIn;

const importedId = '15b82c55-a517-4525-8c92-ebf94522760b';
Map<String, dynamic> importedWorkout() => record(importedId, 'workout', {
  'name': 'Imported Workout',
  'source_name': 'ride.zwo',
  'blocks': [
    {'type': 'steady', 'duration_sec': 300, 'target_watts': 180},
  ],
});

void main() {
  test('uploads raw ZWO and accepts only refreshed imported workout', () async {
    final (account, http) = await signedIn();
    final controller = WorkoutImportController(account);
    final imported = importedWorkout();
    http.json({
      'records': [imported],
    });
    http.json({
      'records': [profile(), imported],
    });
    final source = utf8.encode(
      '<workout_file><name>Imported Workout</name></workout_file>',
    );

    expect(await controller.import('folder/ride.zwo', source), isTrue);

    expect(controller.imported?.name, 'Imported Workout');
    expect(controller.error, isNull);
    final request = http.requests[2];
    expect(request.method, 'POST');
    expect(request.uri.path, '/api/v1/import');
    expect(request.uri.queryParameters, {'filename': 'ride.zwo'});
    expect(request.headers['Authorization'], 'Bearer test-only-token');
    expect(request.headers['Content-Type'], 'application/xml');
    expect(request.body, isNull);
    expect(request.bytes, source);
    expect(http.requests[3].uri.path, '/api/v1/sync');
  });

  test('uploads raw JSON without wrapping or logging content', () async {
    final (account, http) = await signedIn();
    final controller = WorkoutImportController(account);
    final imported = importedWorkout();
    http.json({
      'records': [imported],
    });
    http.json({
      'records': [profile(), imported],
    });
    final source = <int>[
      0xef,
      0xbb,
      0xbf,
      ...utf8.encode('{"name":"Imported Workout","blocks":[]}'),
    ];

    expect(await controller.import('ride.JSON', source), isTrue);
    expect(http.requests[2].headers['Content-Type'], 'application/json');
    expect(http.requests[2].body, isNull);
    expect(http.requests[2].bytes, source);
  });

  test('extension, empty file and 2 MB limit are enforced locally', () async {
    final invalid = [
      (name: 'ride.txt', content: utf8.encode('data')),
      (name: 'ride.zwo', content: <int>[]),
      (name: 'ride.json', content: List.filled(2000001, 120)),
    ];
    for (final item in invalid) {
      final (account, http) = await signedIn();
      final controller = WorkoutImportController(account);
      final requestsBefore = http.requests.length;
      expect(await controller.import(item.name, item.content), isFalse);
      expect(controller.error, isNotNull);
      expect(http.requests, hasLength(requestsBefore));
    }
  });

  for (final status in [401, 409, 422, 500]) {
    test('import HTTP $status stays visible and is not successful', () async {
      final (account, http) = await signedIn();
      final controller = WorkoutImportController(account);
      http.json({'detail': 'Invalid import'}, status);

      expect(
        await controller.import('ride.zwo', utf8.encode('<invalid/>')),
        isFalse,
      );
      expect(controller.imported, isNull);
      expect(controller.error, isNotNull);
      if (status == 401) expect(account.user, isNull);
    });
  }

  test('network and malformed acknowledgement never report import', () async {
    final (offlineAccount, _) = await signedIn();
    final offline = WorkoutImportController(offlineAccount);
    expect(await offline.import('ride.json', utf8.encode('{}')), isFalse);
    expect(offline.error, contains('Server nicht erreichbar'));

    final (account, http) = await signedIn();
    final malformed = WorkoutImportController(account);
    http.json({'records': []});
    expect(
      await malformed.import(
        'ride.json',
        utf8.encode(jsonEncode({'name': 'x'})),
      ),
      isFalse,
    );
    expect(malformed.imported, isNull);
    expect(http.requests, hasLength(3));
  });

  testWidgets('catalog picker imports and opens the authoritative workout', (
    tester,
  ) async {
    final (account, http) = await signedIn();
    final imported = importedWorkout();
    http.json({
      'records': [imported],
    });
    http.json({
      'records': [profile(), imported],
    });
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AnimatedBuilder(
            animation: account,
            builder: (context, _) => CatalogPage(
              account: account,
              workouts: true,
              onSelect: (_, _) {},
              pickWorkoutImport: () async => WorkoutImportSource(
                'ride.zwo',
                utf8.encode('<workout_file/>'),
              ),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('importWorkout')));
    await tester.pumpAndSettle();

    expect(find.text('Workout bearbeiten'), findsOneWidget);
    expect(find.text('Imported Workout'), findsOneWidget);
    expect(http.requests[2].uri.path, '/api/v1/import');
  });

  testWidgets('picker read error is visible without network request', (
    tester,
  ) async {
    final (account, http) = await signedIn();
    final before = http.requests.length;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CatalogPage(
            account: account,
            workouts: true,
            onSelect: (_, _) {},
            pickWorkoutImport: () => throw const FormatException('bad file'),
          ),
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('importWorkout')));
    await tester.pumpAndSettle();

    expect(
      find.text('Die Importdatei konnte nicht gelesen werden.'),
      findsOneWidget,
    );
    expect(http.requests, hasLength(before));
  });
}
