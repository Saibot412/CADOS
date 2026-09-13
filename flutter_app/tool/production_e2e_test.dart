import 'dart:io';
import 'dart:math';

import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/features/account/api.dart';
import 'package:cados_app/infrastructure/account/production_stores.dart';
import 'package:collection/collection.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

/// Explicit, credential-gated production smoke test. It is outside test/ so the
/// normal test suite can never contact production accidentally.
///
/// Required environment variables:
///   CADOS_E2E_EMAIL
///   CADOS_E2E_PASSWORD
/// Optional:
///   CADOS_E2E_SERVER (defaults to https://cados.saibot.at)
class _MemoryStore implements TokenStore, ConfigStore {
  final tokens = <String, String>{};
  String? origin;

  @override
  Future<String?> read([String? server]) async =>
      server == null ? origin : tokens[server];

  @override
  Future<void> write(String value, [String? token]) async {
    if (token == null) {
      origin = value;
    } else {
      tokens[value] = token;
    }
  }

  @override
  Future<void> delete(String server) async => tokens.remove(server);
}

class _OfflineTransport implements ApiTransport {
  Never _offline() =>
      throw const SocketException('intentional E2E offline probe');

  @override
  Future<HttpReply> send(
    String method,
    Uri uri,
    Map<String, String> headers,
    String? body,
  ) async => _offline();

  @override
  Future<HttpReply> sendBytes(
    String method,
    Uri uri,
    Map<String, String> headers,
    List<int> body,
  ) async => _offline();
}

String _uuidV4() {
  final bytes = List<int>.generate(16, (_) => Random.secure().nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
      '${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

Map<String, dynamic> _workout(
  String id, {
  required int revision,
  bool deleted = false,
}) => {
  'id': id,
  'kind': 'workout',
  'revision': revision,
  'deleted': deleted,
  'shared': false,
  'payload': {
    'name': 'CADOS production E2E temporary workout',
    'description': 'Temporary automated verification record; safe to delete.',
    'blocks': [
      {'type': 'steady', 'duration_sec': 1, 'target_watts': 100},
    ],
  },
};

Map<String, dynamic> _sessionEntry({
  required String id,
  required String accountId,
  required String server,
  required int ftp,
}) {
  final now = DateTime.now().toUtc().toIso8601String();
  final workout = _workout(_uuidV4(), revision: 0)['payload'];
  return {
    'server': server,
    'account_id': accountId,
    'record': {
      'id': id,
      'kind': 'session',
      'revision': 0,
      'deleted': false,
      'shared': false,
      'payload': {
        'id': id,
        'user_id': accountId,
        'user_name': 'CADOS E2E',
        'workout_name': 'CADOS production E2E temporary session',
        'duration_sec': 0,
        'workout_elapsed_sec': 0,
        'status': 'stopped',
        'trainer_source': 'production_e2e_no_hardware',
        'started_at': now,
        'timestamp': now,
        'ftp_watts': ftp,
        'workout_payload': workout,
        'metrics': <String, num>{},
        'samples': <Map<String, dynamic>>[],
      },
    },
  };
}

void main() {
  final email = Platform.environment['CADOS_E2E_EMAIL'] ?? '';
  final password = Platform.environment['CADOS_E2E_PASSWORD'] ?? '';
  final server =
      Platform.environment['CADOS_E2E_SERVER'] ?? ApiConfig.defaultUrl;

  test('production login, restore, sync, mutation, conflict and cleanup', () async {
    if (email.isEmpty || password.isEmpty) {
      fail('CADOS_E2E_EMAIL und CADOS_E2E_PASSWORD müssen gesetzt sein.');
    }

    final config = ApiConfig(server);
    final store = _MemoryStore()..origin = config.base.toString();
    final client = http.Client();
    final transport = HttpApiTransport(client);
    AccountController? account;
    String? workoutId;
    String? sessionId;

    try {
      final login = AccountController(transport, store, store);
      await login.login(email, password);
      expect(login.error, isNull);
      expect(login.user, isNotNull);
      expect(login.catalog, isNotNull);
      expect(store.tokens[config.base.toString()], isNotEmpty);
      login.dispose();

      // A fresh controller proves the stored-token /auth/me + /sync restore path.
      account = AccountController(transport, store, store);
      await account.restore();
      expect(account.error, isNull);
      expect(account.user, isNotNull);
      expect(account.catalog, isNotNull);

      workoutId = _uuidV4();
      final createdWorkout = await account.mutateRecord(
        _workout(workoutId, revision: 0),
        expectedGeneration: account.syncGeneration,
      );
      expect(createdWorkout.revision, greaterThan(0));
      expect(
        account.catalog!.records
            .singleWhere((record) => record.id == workoutId)
            .revision,
        createdWorkout.revision,
      );

      // The same stale revision must be rejected and must not overwrite production.
      await expectLater(
        account.mutateRecord(
          _workout(workoutId, revision: 0),
          expectedGeneration: account.syncGeneration,
        ),
        throwsA(isA<ApiFailure>().having((e) => e.status, 'status', 409)),
      );
      await account.refresh();
      expect(account.error, isNull);

      sessionId = _uuidV4();
      final profileFtp = account.catalog!.profiles
          .map((profile) => profile.ftp)
          .whereType<int>()
          .firstOrNull;
      await account.uploadSession(
        _sessionEntry(
          id: sessionId,
          accountId: account.user!.id,
          server: config.base.toString(),
          ftp: profileFtp ?? 200,
        ),
      );
      expect(account.error, isNull);
      final createdSession = account.catalog!.records.singleWhere(
        (record) => record.id == sessionId,
      );
      expect(createdSession.revision, greaterThan(0));

      final unauthorized = CadosApi(transport, config);
      await expectLater(
        unauthorized.request(
          '/auth/me',
          token: 'intentional-invalid-e2e-token',
        ),
        throwsA(isA<ApiFailure>().having((e) => e.status, 'status', 401)),
      );
      await expectLater(
        CadosApi(
          _OfflineTransport(),
          config,
        ).request('/sync', token: 'not-sent'),
        throwsA(isA<ApiFailure>().having((e) => e.status, 'status', isNull)),
      );
    } finally {
      // Tombstones preserve sync history while removing both temporary records
      // from every active product view. Cleanup is retried and an unavailable
      // authoritative snapshot is a failure, never evidence of zero leftovers.
      Object? cleanupFailure;
      if (account != null) {
        try {
          for (final id in [sessionId, workoutId].whereType<String>()) {
            Object? lastFailure;
            var cleaned = false;
            for (var attempt = 0; attempt < 3 && !cleaned; attempt++) {
              try {
                await account.refresh();
                if (account.error != null || account.catalog == null) {
                  throw StateError(
                    'Authoritative cleanup snapshot unavailable.',
                  );
                }
                final record = account.catalog!.records
                    .where(
                      (candidate) => candidate.id == id && !candidate.deleted,
                    )
                    .firstOrNull;
                if (record == null) {
                  cleaned = true;
                  continue;
                }
                await account.mutateRecord({
                  ...record.toJson(),
                  'deleted': true,
                }, expectedGeneration: account.syncGeneration);
                cleaned = true;
              } catch (error) {
                lastFailure = error;
              }
            }
            if (!cleaned) {
              throw StateError(
                'Temporary production record cleanup failed: $lastFailure',
              );
            }
          }
          await account.refresh();
          if (account.error != null || account.catalog == null) {
            throw StateError(
              'Final authoritative cleanup snapshot unavailable.',
            );
          }
          final leftovers = account.catalog!.records
              .where(
                (record) =>
                    (record.id == workoutId || record.id == sessionId) &&
                    !record.deleted,
              )
              .length;
          if (leftovers != 0) {
            throw StateError('Temporary production records remain active.');
          }
        } catch (error) {
          cleanupFailure = error;
        }
        try {
          await account.logout();
        } finally {
          account.dispose();
        }
      }
      client.close();
      if (cleanupFailure != null) {
        fail(
          'Production cleanup could not be authoritatively confirmed: $cleanupFailure',
        );
      }
    }
  }, timeout: const Timeout(Duration(minutes: 2)));
}
