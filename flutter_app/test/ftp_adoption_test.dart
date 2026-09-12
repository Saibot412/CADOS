import 'dart:convert';

import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/features/session/ftp_adoption_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show TestHttp, TestStore, record, testUser;

Map<String, dynamic> profile({int ftp = 250, int revision = 3}) {
  final value = record('profile', 'profile', {
    'id': 'profile',
    'name': 'Rider',
    'ftp': ftp,
  });
  value['revision'] = revision;
  return value;
}

Map<String, dynamic> ftpSession({bool eligible = true, bool applied = false}) =>
    record('session', 'session', {
      'status': 'completed',
      'workout_name': 'FTP Ramp Test (ERG)',
      'timestamp': '2026-09-12T06:00:00Z',
      'duration_sec': 1200,
      'ftp_test_result': {
        'eligible': eligible,
        'old_ftp': 250,
        'method': '75_percent_best_continuous_minute',
        if (eligible) 'best_minute_watts': 360,
        if (eligible) 'estimated_ftp': 270,
        if (!eligible) 'reason': 'Keine vollständige Belastungsminute.',
        if (applied) 'applied_at': '2026-09-12T06:30:00Z',
      },
    });

Future<(AccountController, TestHttp)> signedIn(
  List<Map<String, dynamic>> records,
) async {
  final http = TestHttp(), store = TestStore();
  final account = AccountController(http, store, store);
  http.json({'token': 'test-only-token', 'user': testUser});
  http.json({'records': records});
  await account.login('rider@example.invalid', 'test-only-password');
  return (account, http);
}

void main() {
  test('eligible FTP result is adopted with current profile revision and refreshed', () async {
    final (account, http) = await signedIn([profile(), ftpSession()]);
    final controller = FtpAdoptionController(account);
    http.json({'ftp': 270});
    http.json(testUser);
    http.json({
      'records': [profile(ftp: 270, revision: 4), ftpSession(applied: true)],
    });

    await controller.adopt(account.catalog!.sessions.single);

    expect(controller.error, isNull);
    expect(controller.applied, isTrue);
    expect(account.catalog!.profiles.single.ftp, 270);
    final request = http.requests
        .where((r) => r.uri.path == '/api/v1/sessions/session/ftp')
        .single;
    expect(request.method, 'POST');
    expect(jsonDecode(request.body!), {'profile_revision': 3});
    expect(request.headers['Authorization'], 'Bearer test-only-token');
  });

  for (final session in [
    ftpSession(eligible: false),
    ftpSession(applied: true),
  ]) {
    test(
      'ineligible or already applied result never mutates the profile',
      () async {
        final (account, http) = await signedIn([profile(), session]);
        final before = http.requests.length;
        final controller = FtpAdoptionController(account);
        await controller.adopt(account.catalog!.sessions.single);
        expect(http.requests.length, before);
        expect(controller.error, isNotNull);
        expect(controller.applied, isFalse);
      },
    );
  }

  test('server conflict remains visible and keeps current catalog', () async {
    final (account, http) = await signedIn([profile(), ftpSession()]);
    final original = account.catalog;
    http.json({}, 409);
    final controller = FtpAdoptionController(account);

    await controller.adopt(account.catalog!.sessions.single);

    expect(controller.error, contains('409'));
    expect(controller.applied, isFalse);
    expect(account.catalog, same(original));
    expect(account.catalog!.profiles.single.ftp, 250);
  });
}
