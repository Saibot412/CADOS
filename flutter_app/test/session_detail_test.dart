import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/presentation/catalog_pages.dart';
import 'package:cados_app/presentation/session_detail.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show TestHttp, TestStore, record, testUser;

Map<String, dynamic> detailedSession() => record('session-detail', 'session', {
  'plan_id': 'plan-1',
  'status': 'completed',
  'workout_name': 'FTP Ramp Test (ERG)',
  'workout_file_name': 'ftp-ramp.json',
  'workout_payload': {
    'name': 'FTP Ramp Test (ERG)',
    'blocks': [
      {'type': 'steady', 'duration_sec': 1200, 'target_watts': 300},
    ],
  },
  'timestamp': '2026-09-12T06:30:00Z',
  'started_at': '2026-09-12T06:00:00Z',
  'duration_sec': 1200,
  'workout_elapsed_sec': 1180,
  'ftp_watts': 250,
  'trainer_source': 'bluetooth_ftms',
  'metrics': {
    'avg_watts': 231,
    'max_watts': 420,
    'normalized_power': 255,
    'intensity_factor': 1.02,
    'tss': 34.7,
    'work_kj': 277.2,
    'avg_cadence': 89,
    'max_cadence': 112,
    'avg_heart_rate': 158,
    'max_heart_rate': 191,
  },
  'samples': [
    {
      'duration_sec': 1,
      'elapsed_sec': 1,
      'workout_elapsed_sec': 0,
      'watts': 231,
      'cadence': 89,
      'heart_rate': 158,
      'target_watts': 230,
      'segment': 0,
    },
  ],
  'ftp_test_result': {
    'eligible': true,
    'old_ftp': 250,
    'method': '75_percent_best_continuous_minute',
    'best_minute_watts': 360,
    'estimated_ftp': 270,
  },
});

Future<(AccountController, TestHttp)> accountWithSession() async {
  final http = TestHttp(), store = TestStore();
  final account = AccountController(http, store, store);
  http.json({'token': 'test-only-token', 'user': testUser});
  http.json({
    'records': [
      record('profile', 'profile', {
        'id': 'profile',
        'name': 'Rider',
        'ftp': 250,
      }),
      detailedSession(),
    ],
  });
  await account.login('rider@example.invalid', 'test-only-password');
  return (account, http);
}

void main() {
  for (final size in [const Size(430, 900), const Size(1200, 900)]) {
    testWidgets('session detail renders real metrics responsively at $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final (account, http) = await accountWithSession();
      final session = account.catalog!.sessions.single;

      await tester.pumpWidget(
        MaterialApp(
          home: SessionDetailPage(session: session, account: account),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Trainingsergebnis'), findsOneWidget);
      expect(find.text('FTP Ramp Test (ERG)'), findsOneWidget);
      expect(find.text('Ø Leistung'), findsOneWidget);
      expect(find.text('231 W'), findsOneWidget);
      expect(find.text('Normalized Power'), findsOneWidget);
      expect(find.text('255 W'), findsOneWidget);
      expect(find.text('34.7'), findsOneWidget);
      expect(find.text('277.2 kJ'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('FTP-Rampentest'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Ermittelte FTP: 270 W'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('1 echte Messabschnitte gespeichert'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('1 echte Messabschnitte gespeichert'), findsOneWidget);
      expect(tester.takeException(), isNull);

      expect(
        http.requests.where(
          (request) => request.uri.path.contains('/sessions/'),
        ),
        isEmpty,
      );
    });
  }

  testWidgets('keeping the existing FTP never writes to the server', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, http) = await accountWithSession();
    await tester.pumpWidget(
      MaterialApp(
        home: SessionDetailPage(
          session: account.catalog!.sessions.single,
          account: account,
        ),
      ),
    );
    await tester.drag(find.byType(Scrollable).first, const Offset(0, -700));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Bisherige FTP behalten'));
    await tester.pump();
    expect(find.text('Die bisherige FTP bleibt unverändert.'), findsOneWidget);
    expect(
      http.requests.where((request) => request.uri.path.contains('/sessions/')),
      isEmpty,
    );
  });

  testWidgets('FTP adoption requires explicit confirmation', (tester) async {
    tester.view.physicalSize = const Size(800, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, http) = await accountWithSession();
    await tester.pumpWidget(
      MaterialApp(
        home: SessionDetailPage(
          session: account.catalog!.sessions.single,
          account: account,
        ),
      ),
    );
    await tester.drag(find.byType(Scrollable).first, const Offset(0, -700));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('adoptFtp')));
    await tester.pumpAndSettle();
    expect(find.text('FTP wirklich übernehmen?'), findsOneWidget);
    expect(find.textContaining('von 250 W auf 270 W'), findsOneWidget);
    await tester.tap(find.text('Abbrechen'));
    await tester.pumpAndSettle();
    expect(
      http.requests.where((request) => request.uri.path.contains('/sessions/')),
      isEmpty,
    );
  });

  testWidgets('history row opens the synchronized session detail', (
    tester,
  ) async {
    final (account, _) = await accountWithSession();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CatalogPage(
            account: account,
            workouts: false,
            onSelect: (_, _) {},
          ),
        ),
      ),
    );
    await tester.tap(find.text('FTP Ramp Test (ERG)'));
    await tester.pumpAndSettle();
    expect(find.text('Trainingsergebnis'), findsOneWidget);
    expect(find.text('231 W'), findsOneWidget);
  });
}
