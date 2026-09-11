import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/features/account/api.dart';
import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/features/catalog/records.dart';

class TestStore implements TokenStore, ConfigStore {
  final tokens = <String, String>{};
  String? origin;
  bool failWrite = false;
  @override
  Future<String?> read([String? server]) async =>
      server == null ? origin : tokens[server];
  @override
  Future<void> write(String value, [String? token]) async {
    if (failWrite) throw StateError('storage unavailable');
    if (token == null) {
      origin = value;
    } else {
      tokens[value] = token;
    }
  }

  @override
  Future<void> delete(String server) async {
    tokens.remove(server);
  }
}

class TestHttp implements ApiTransport {
  final replies = <HttpReply>[];
  final requests =
      <({String method, Uri uri, Map<String, String> headers, String? body})>[];
  @override
  Future<HttpReply> send(
    String method,
    Uri uri,
    Map<String, String> headers,
    String? body,
  ) async {
    requests.add((method: method, uri: uri, headers: headers, body: body));
    return replies.removeAt(0);
  }

  void json(Object value, [int status = 200]) =>
      replies.add(HttpReply(status, jsonEncode(value)));
}

const testUser = {
  'id': 'account',
  'email': 'rider@example.invalid',
  'admin': false,
  'active': true,
};
Map<String, dynamic> record(
  String id,
  String kind,
  Map<String, dynamic> payload, {
  bool deleted = false,
  bool shared = false,
}) => {
  'id': id,
  'kind': kind,
  'revision': 3,
  'deleted': deleted,
  'shared': shared,
  'publisher': {'name': 'CADOS'},
  'payload': payload,
  'extension': 'retained',
};
void main() {
  test('snapshot envelopes are recursively immutable and malformed shapes are rejected', () {
    final raw = record('w', 'workout', {
      'name': 'Server workout',
      'blocks': [
        {'type': 'steady', 'duration_sec': 30, 'target_watts': 100},
      ],
      'future': {'x': 1},
    });
    final parsed = Catalog.fromJson({
      'records': [raw],
    });
    (raw['payload'] as Map)['name'] = 'Mutated';
    expect(parsed.workouts.single.name, 'Server workout');
    expect(
      () => (parsed.workouts.single.record.payload['future'] as Map)['x'] = 2,
      throwsUnsupportedError,
    );
    for (final response in <Map<String, dynamic>>[
      {'records': {}},
      {
        'records': [{}],
      },
      {
        'records': [raw, raw],
      },
    ]) {
      expect(() => Catalog.fromJson(response), throwsFormatException);
    }
  });

  test('malformed snapshot is rejected before presentation; opaque tombstones survive', () {
    expect(
      () => Catalog.fromJson({
        'records': [
          record('w', 'workout', {
            'name': 'Broken',
            'blocks': [
              {'type': 'steady'},
            ],
          }),
        ],
      }),
      throwsFormatException,
    );
    expect(
      () => Catalog.fromJson({
        'records': [
          record('p', 'plan', {
            'date': '2026-02-30',
            'workout_id': 'w',
            'workout_name': 'Plan',
          }),
        ],
      }),
      throwsFormatException,
    );
    expect(
      Catalog.fromJson({
        'records': [record('gone', 'workout', {}, deleted: true)],
      }).workouts,
      isEmpty,
    );
  });
  test(
    'failed refresh removes previously loaded snapshot and reports offline',
    () async {
      final http = TestHttp(), store = TestStore();
      final a = AccountController(http, store, store);
      http.json({'token': 'test-only-token', 'user': testUser});
      http.json({'records': []});
      await a.login('rider@example.invalid', 'test-only-password');
      expect(a.catalog, isNotNull);
      await a.refresh();
      expect(a.catalog, isNull);
      expect(a.error, contains('nicht erreichbar'));
    },
  );

  test('config validates origins and composes exact API paths', () {
    expect(
      ApiConfig(ApiConfig.defaultUrl).endpoint('/auth/me').toString(),
      'https://cados.saibot.at/api/v1/auth/me',
    );
    for (final bad in [
      'http://example.com',
      'https://user:secret@example.com',
      'https://example.com/api/v1',
      'https://example.com?q=x',
      'not a url',
    ]) {
      expect(() => ApiConfig(bad), throwsFormatException);
    }
  });
  test(
    'login uses exact payload, persists token, loads snapshot, revokes logout',
    () async {
      final http = TestHttp(), store = TestStore();
      final a = AccountController(http, store, store);
      http.json({'token': 'test-only-token', 'user': testUser});
      http.json({'records': []});
      await a.login(' rider@example.invalid ', 'test-only-password');
      expect(a.user!.id, 'account');
      expect(a.catalog!.records, isEmpty);
      expect(jsonDecode(http.requests.first.body!), {
        'email': 'rider@example.invalid',
        'password': 'test-only-password',
      });
      expect(
        http.requests.last.headers['Authorization'],
        'Bearer test-only-token',
      );
      expect(store.tokens.values.single, 'test-only-token');
      http.json({'ok': true});
      await a.logout();
      expect(http.requests.last.uri.path, '/api/v1/auth/logout');
      expect(a.user, isNull);
      expect(store.tokens, isEmpty);
    },
  );
  test('restore validates /me; 401 clears local account and token', () async {
    final http = TestHttp(), store = TestStore();
    store.tokens[ApiConfig.defaultUrl] = 'test-only-token';
    final a = AccountController(http, store, store);
    http.json(testUser);
    http.json({'records': []});
    await a.restore();
    expect(http.requests.first.uri.path, '/api/v1/auth/me');
    http.json({}, 401);
    await a.refresh();
    expect(a.user, isNull);
    expect(a.catalog, isNull);
    expect(store.tokens, isEmpty);
  });
  test(
    'offline restore preserves token for retry and shows error, no data',
    () async {
      final http = TestHttp(), store = TestStore();
      store.tokens[ApiConfig.defaultUrl] = 'test-only-token';
      final a = AccountController(http, store, store);
      await a.restore();
      expect(a.error, contains('nicht erreichbar'));
      expect(a.user, isNull);
      expect(a.catalog, isNull);
      expect(store.tokens, isNotEmpty);
      await a.changeServer('https://other.example');
      await a.refresh();
      expect(http.requests.length, 1);
      expect(a.user, isNull);
    },
  );
  test('storage failure revokes issued token and never signs in', () async {
    final http = TestHttp(), store = TestStore()..failWrite = true;
    final a = AccountController(http, store, store);
    http.json({'token': 'test-only-token', 'user': testUser});
    http.json({'ok': true});
    await a.login('rider@example.invalid', 'test-only-password');
    expect(a.user, isNull);
    expect(a.error, isNotNull);
    expect(http.requests.last.uri.path, '/api/v1/auth/logout');
  });
  test('snapshot preserves unknowns, revisions, tombstones and shared visibility; only completed plan links count', () {
    final shared = record('w', 'workout', {
      'name': 'Real server workout',
      'blocks': [
        {
          'type': 'ramp',
          'duration_sec': 90,
          'start_pct_ftp': 0.5,
          'end_watts': 250.5,
        },
      ],
      'future': {'x': 1},
    }, shared: true);
    final c = Catalog.fromJson({
      'records': [
        shared,
        record('gone', 'workout', {}, deleted: true),
        record('profile', 'profile', {'name': 'Rider', 'ftp': 245}),
        record('p', 'plan', {
          'workout_id': 'w',
          'workout_name': 'Planned',
          'date': '2026-09-11',
        }),
        record('next', 'plan', {
          'workout_id': 'w',
          'workout_name': 'Next',
          'date': '2026-09-12',
        }),
        record('s', 'session', {
          'plan_id': 'p',
          'status': 'completed',
          'timestamp': '2026-09-11T08:00:00Z',
          'duration_sec': 90,
          'workout_name': 'Planned',
        }),
        record('s2', 'session', {
          'plan_id': 'next',
          'status': 'stopped',
          'timestamp': '2026-09-11T09:00:00Z',
          'duration_sec': 10,
          'workout_name': 'Next',
        }),
      ],
    });
    expect(c.workouts.single.record.toJson(), shared);
    expect(c.workouts.single.duration, 90);
    expect(c.workouts.single.blocks.single.endWatts, 250.5);
    expect(c.profiles.single.ftp, 245);
    expect(c.upcoming(DateTime(2026, 9, 11)).single.record.id, 'next');
    expect(c.records.length, 7);
  });
}
