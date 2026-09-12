import 'dart:convert';

import 'package:cados_app/features/catalog/records.dart';
import 'package:cados_app/features/profile/profile_editor_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import 'record_mutation_test.dart' show profile, profileId, signedIn;

void main() {
  test('malformed synchronized profile values are rejected before UI', () {
    final invalidValues = <String, Object?>{
      'name': '',
      'ftp': 29,
      'weight_kg': double.nan,
      'max_hr': 251,
    };
    for (final entry in invalidValues.entries) {
      final raw = profile();
      (raw['payload'] as Map<String, dynamic>)[entry.key] = entry.value;
      expect(
        () => Catalog.fromJson({
          'records': [raw],
        }),
        throwsFormatException,
        reason: entry.key,
      );
    }
  });

  test(
    'valid profile edit preserves opaque fields and reloads authority',
    () async {
      final (account, http) = await signedIn();
      final controller = ProfileEditorController(
        account,
        account.catalog!.profiles.single,
      );
      final saved = profile(revision: 4);
      final savedPayload = saved['payload'] as Map<String, dynamic>;
      savedPayload
        ..['name'] = 'Updated Rider'
        ..['ftp'] = 280
        ..['weight_kg'] = 73.5
        ..['max_hr'] = 195;
      http.json({
        'records': [saved],
      });
      http.json({
        'records': [saved],
      });

      expect(
        await controller.save(
          name: '  Updated Rider  ',
          ftp: '280',
          weightKg: '73,5',
          maxHeartRate: '195',
        ),
        isTrue,
      );

      expect(controller.error, isNull);
      expect(controller.profile.name, 'Updated Rider');
      final change =
          (jsonDecode(http.requests[2].body!)['changes'] as List).single;
      expect(change['id'], profileId);
      expect(change['revision'], 3);
      expect(change['payload']['future'], {'retained': true});
      expect(change['payload']['weight_kg'], 73.5);
      expect(change['payload']['updated_at'], isA<String>());
      expect(DateTime.tryParse(change['payload']['updated_at']), isNotNull);
    },
  );

  test('optional weight and max HR may remain absent', () async {
    final (account, http) = await signedIn();
    final controller = ProfileEditorController(
      account,
      account.catalog!.profiles.single,
    );
    final saved = profile(revision: 4);
    (saved['payload'] as Map<String, dynamic>)
      ..['weight_kg'] = null
      ..['max_hr'] = null;
    http.json({
      'records': [saved],
    });
    http.json({
      'records': [saved],
    });

    expect(
      await controller.save(
        name: 'Rider',
        ftp: '250',
        weightKg: '',
        maxHeartRate: '',
      ),
      isTrue,
    );
    final payload = (jsonDecode(http.requests[2].body!)['changes'] as List)
        .single['payload'];
    expect(payload['weight_kg'], isNull);
    expect(payload['max_hr'], isNull);
  });

  test('invalid fields are rejected locally without a request', () async {
    final cases = [
      (name: '', ftp: '250', weight: '72', maxHr: '190'),
      (
        name: List.filled(201, 'x').join(),
        ftp: '250',
        weight: '72',
        maxHr: '190',
      ),
      (name: 'Rider', ftp: '29', weight: '72', maxHr: '190'),
      (name: 'Rider', ftp: '2001', weight: '72', maxHr: '190'),
      (name: 'Rider', ftp: '250.5', weight: '72', maxHr: '190'),
      (name: 'Rider', ftp: '250', weight: '9.9', maxHr: '190'),
      (name: 'Rider', ftp: '250', weight: '501', maxHr: '190'),
      (name: 'Rider', ftp: '250', weight: 'NaN', maxHr: '190'),
      (name: 'Rider', ftp: '250', weight: '72', maxHr: '49'),
      (name: 'Rider', ftp: '250', weight: '72', maxHr: '251'),
      (name: 'Rider', ftp: '250', weight: '72', maxHr: '190.5'),
    ];
    for (final values in cases) {
      final (account, http) = await signedIn();
      final controller = ProfileEditorController(
        account,
        account.catalog!.profiles.single,
      );
      final requestsBefore = http.requests.length;

      expect(
        await controller.save(
          name: values.name,
          ftp: values.ftp,
          weightKg: values.weight,
          maxHeartRate: values.maxHr,
        ),
        isFalse,
        reason: values.toString(),
      );
      expect(controller.error, isNotNull);
      expect(http.requests, hasLength(requestsBefore));
    }
  });

  test(
    'revision conflict is visible and does not replace local profile',
    () async {
      final (account, http) = await signedIn();
      final original = account.catalog!.profiles.single;
      final controller = ProfileEditorController(account, original);
      http.json({}, 409);

      expect(
        await controller.save(
          name: 'Unsaved Rider',
          ftp: '280',
          weightKg: '73',
          maxHeartRate: '195',
        ),
        isFalse,
      );
      expect(controller.error, contains('409'));
      expect(controller.profile, same(original));
      expect(account.catalog!.profiles.single.name, 'Rider');
    },
  );
}
