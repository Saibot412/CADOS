import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/features/session/session_sync_controller.dart';
import 'package:cados_app/features/session/session_payload.dart';
import 'package:cados_app/infrastructure/session/file_session_journal.dart';

import 'account_test.dart' show TestHttp, TestStore, testUser;
import 'session_journal_test.dart' show journalData;

void main() {
  late Directory dir;
  late FileSessionJournal journal;
  late TestHttp http;
  late AccountController account;
  late SessionSyncController sync;
  late Map<String, dynamic> entry, saved;
  setUp(() async {
    dir = await Directory.systemTemp.createTemp('cados-outbox-test-');
    journal = FileSessionJournal(File('${dir.path}/journal.json'));
    http = TestHttp();
    final store = TestStore();
    account = AccountController(http, store, store);
    http.json({'token': 'test-only-token', 'user': testUser});
    http.json({'records': []});
    await account.login('rider@example.invalid', 'test-only-password');
    entry = journalData().finalize('stopped', DateTime.utc(2026, 9, 11));
    saved = copyJson(entry['record'] as Map<String, dynamic>);
    saved['revision'] = 1;
    saved['publisher'] = null;
    final payload = saved['payload'] as Map;
    payload['metrics'] = {'max_heart_rate': 145};
    payload['ftp_test_result'] = null;
    await journal.finalize(entry);
    sync = SessionSyncController(
      account: account,
      journal: journal,
      uploader: AccountSessionUploader(account),
    );
  });
  tearDown(() async {
    sync.dispose();
    await sync.closed;
    account.dispose();
    await dir.delete(recursive: true);
  });
  test('POST exact revision-zero envelope, refresh profile side effects, remove only after success', () async {
    http.json({'records': []});
    http.json({
      'records': [saved],
    });
    http.json({
      'records': [
        saved,
        {
          'id': '395599cb-cc7b-409d-bfef-50d70e8adf8b',
          'kind': 'profile',
          'revision': 2,
          'deleted': false,
          'shared': false,
          'payload': {'name': 'Rider', 'ftp': 250, 'max_hr': 145},
        },
      ],
    });
    await sync.retry();
    expect(sync.pending, 0);
    expect((await journal.load()).outbox, isEmpty);
    expect(account.catalog!.profiles.single.maxHr, 145);
    final post = http.requests
        .where((r) => r.uri.path == '/api/v1/sync' && r.method == 'POST')
        .single;
    expect(jsonDecode(post.body!), {
      'changes': [entry['record']],
    });
    expect(post.headers['Authorization'], 'Bearer test-only-token');
  });
  for (final status in [401, 409, 500]) {
    test(
      'HTTP $status retains durable outbox and does not report synced',
      () async {
        http.json({'records': []});
        http.json({}, status);
        await sync.retry();
        expect(sync.pending, 1);
        expect(sync.error, isNotNull);
        expect(
          (await FileSessionJournal(journal.file).load()).outbox.length,
          1,
        );
        if (status == 401) expect(account.user, isNull);
      },
    );
  }
  test('lost success response remains pending, next snapshot acknowledges same stable session without duplicate POST', () async {
    http.json({
      'records': [],
    }); // POST has no reply: simulated transport failure.
    await sync.retry();
    expect(sync.pending, 1);
    http.json({
      'records': [saved],
    });
    await sync.retry();
    expect(sync.pending, 0);
    expect(
      http.requests
          .where((r) => r.uri.path == '/api/v1/sync' && r.method == 'POST')
          .length,
      1,
    );
  });
  test('matching ID with different data is a conflict and never overwritten or deleted', () async {
    (saved['payload'] as Map)['workout_name'] = 'Different workout';
    http.json({
      'records': [saved],
    });
    await sync.retry();
    expect(sync.pending, 1);
    expect((await journal.load()).outbox.length, 1);
    expect(
      http.requests.where(
        (r) => r.method == 'POST' && r.uri.path == '/api/v1/sync',
      ),
      isEmpty,
    );
  });
  test('unrelated account/server entries never upload', () async {
    account.user = null;
    await sync.retry();
    expect(sync.pending, 1);
    expect(http.requests.length, 2);
  });
  test('successful POST with malformed acknowledgement or failed refresh keeps durable entry', () async {
    http.json({'records': []});
    http.json({'records': []});
    await sync.retry();
    expect(sync.pending, 1);
    http.json({'records': []});
    http.json({
      'records': [saved],
    }); // refresh unavailable
    await sync.retry();
    expect(sync.pending, 1);
    expect(sync.error, isNotNull);
  });
  test(
    'authenticated refresh automatically retries persisted outbox',
    () async {
      http.json(testUser);
      http.json({'records': []});
      http.json({
        'records': [saved],
      });
      await account.refresh();
      await sync.closed;
      expect(sync.pending, 0);
    },
  );
}
