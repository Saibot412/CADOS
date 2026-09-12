import 'dart:convert';

import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/features/catalog/record_mutation_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_test.dart' show TestHttp, TestStore, record, testUser;

const profileId = '395599cb-cc7b-409d-bfef-50d70e8adf8b';

Map<String, dynamic> profile({int revision = 3, bool deleted = false}) => {
  ...record(profileId, 'profile', {
    'id': profileId,
    'name': 'Rider',
    'ftp': 250,
    'weight_kg': 72.5,
    'max_hr': 190,
    'created_at': '2026-01-01T00:00:00Z',
    'updated_at': '2026-01-01T00:00:00Z',
    'future': {'retained': true},
  }, deleted: deleted),
  'revision': revision,
};

Future<(AccountController, TestHttp)> signedIn() async {
  final http = TestHttp(), store = TestStore();
  final account = AccountController(http, store, store);
  http.json({'token': 'test-only-token', 'user': testUser});
  http.json({
    'records': [profile()],
  });
  await account.login('rider@example.invalid', 'test-only-password');
  return (account, http);
}

void main() {
  test(
    'update preserves opaque payload and accepts only refreshed authority',
    () async {
      final (account, http) = await signedIn();
      final controller = RecordMutationController(account);
      final current = account.catalog!.profiles.single.record;
      final updatedPayload = {
        ...current.payload,
        'name': 'Updated Rider',
        'ftp': 275,
      };
      final saved = profile(revision: 4);
      (saved['payload'] as Map<String, dynamic>)
        ..['name'] = 'Updated Rider'
        ..['ftp'] = 275;
      http.json({
        'records': [saved],
      });
      http.json({
        'records': [saved],
      });

      final result = await controller.update(current, updatedPayload);

      expect(result, isTrue);
      expect(controller.error, isNull);
      expect(account.catalog!.profiles.single.name, 'Updated Rider');
      expect(account.catalog!.profiles.single.record.revision, 4);
      final post = http.requests[2];
      expect(post.method, 'POST');
      expect(post.uri.path, '/api/v1/sync');
      final body = jsonDecode(post.body!) as Map<String, dynamic>;
      expect(body['changes'], [
        {
          'id': profileId,
          'kind': 'profile',
          'revision': 3,
          'deleted': false,
          'shared': false,
          'payload': updatedPayload,
        },
      ]);
      expect((body['changes'] as List).single['payload']['future'], {
        'retained': true,
      });
      expect(http.requests[3].method, 'GET');
      expect(http.requests[3].uri.path, '/api/v1/sync');
    },
  );

  test('create uses revision zero and delete uses current revision', () async {
    final (account, http) = await signedIn();
    const workoutId = 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d';
    final workoutPayload = {
      'name': 'Created workout',
      'blocks': [
        {'type': 'steady', 'duration_sec': 60, 'target_watts': 150},
      ],
    };
    Map<String, dynamic> workout({
      required int revision,
      bool deleted = false,
    }) => {
      ...record(workoutId, 'workout', workoutPayload, deleted: deleted),
      'revision': revision,
    };
    final create = RecordMutationController(account);
    final created = workout(revision: 1);
    http.json({
      'records': [created],
    });
    http.json({
      'records': [profile(), created],
    });
    expect(
      await create.create(
        id: workoutId,
        kind: 'workout',
        payload: workoutPayload,
      ),
      isTrue,
    );
    expect(
      (jsonDecode(http.requests[2].body!)['changes'] as List)
          .single['revision'],
      0,
    );

    final remove = RecordMutationController(account);
    final tombstone = workout(revision: 2, deleted: true);
    http.json({
      'records': [tombstone],
    });
    http.json({
      'records': [profile(), tombstone],
    });
    final currentWorkout = account.catalog!.records.singleWhere(
      (value) => value.id == workoutId,
    );
    expect(await remove.delete(currentWorkout), isTrue);
    final change =
        (jsonDecode(http.requests[4].body!)['changes'] as List).single;
    expect(change['revision'], 1);
    expect(change['deleted'], isTrue);
    expect(account.catalog!.workouts, isEmpty);
  });

  test(
    'stale generation blocks write until caller refreshes its draft',
    () async {
      final (account, http) = await signedIn();
      final controller = RecordMutationController(account);
      http.json(testUser);
      http.json({
        'records': [profile(revision: 4)],
      });
      await account.refresh();
      final requestsBefore = http.requests.length;

      expect(
        await controller.update(
          account.catalog!.records.single,
          Map<String, dynamic>.from(account.catalog!.records.single.payload),
        ),
        isFalse,
      );
      expect(controller.error, contains('neu laden'));
      expect(http.requests, hasLength(requestsBefore));
    },
  );

  for (final status in [401, 409, 422, 500]) {
    test('HTTP $status is visible and never reports saved', () async {
      final (account, http) = await signedIn();
      final original = account.catalog;
      final controller = RecordMutationController(account);
      http.json({}, status);

      expect(
        await controller.update(
          account.catalog!.records.single,
          Map<String, dynamic>.from(account.catalog!.records.single.payload),
        ),
        isFalse,
      );
      expect(controller.error, isNotNull);
      if (status == 409) expect(controller.error, contains('neu laden'));
      expect(controller.saved, isFalse);
      if (status == 401) {
        expect(account.user, isNull);
        expect(account.catalog, isNull);
      } else {
        expect(account.catalog, same(original));
      }
    });
  }

  test(
    'network failure is visible and keeps the authoritative catalog',
    () async {
      final (account, _) = await signedIn();
      final original = account.catalog;
      final controller = RecordMutationController(account);

      expect(
        await controller.update(
          account.catalog!.records.single,
          Map<String, dynamic>.from(account.catalog!.records.single.payload),
        ),
        isFalse,
      );
      expect(controller.error, contains('Server nicht erreichbar'));
      expect(account.catalog, same(original));
    },
  );

  test(
    'malformed acknowledgement never becomes success or refreshes',
    () async {
      final (account, http) = await signedIn();
      final controller = RecordMutationController(account);
      http.json({'records': []});

      expect(
        await controller.update(
          account.catalog!.records.single,
          Map<String, dynamic>.from(account.catalog!.records.single.payload),
        ),
        isFalse,
      );
      expect(controller.saved, isFalse);
      expect(controller.error, isNotNull);
      expect(http.requests, hasLength(3));
    },
  );
}
