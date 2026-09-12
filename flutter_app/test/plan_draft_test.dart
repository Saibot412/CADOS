import 'package:cados_app/features/calendar/plan_draft.dart';
import 'package:cados_app/features/catalog/records.dart';
import 'package:flutter_test/flutter_test.dart';

const planId = '59dfeab3-8f93-4c0f-a95c-8f06a3a4fca3';
const workoutId = 'f31127e1-750d-46c1-922b-9e44d0ae20ef';
const otherWorkoutId = 'da725786-c666-4b60-a3ed-fc2cf372a8a7';

Map<String, dynamic> envelope({
  String id = planId,
  String kind = 'plan',
  int revision = 3,
  bool deleted = false,
  bool shared = false,
  Map<String, dynamic>? payload,
}) => {
  'id': id,
  'kind': kind,
  'revision': revision,
  'deleted': deleted,
  'shared': shared,
  'payload':
      payload ??
      {
        'date': '2026-09-12',
        'workout_id': workoutId,
        'workout_name': 'Threshold',
        'future': {
          'nested': [1, true, null],
        },
      },
};

Map<String, dynamic> workoutEnvelope(
  String id, {
  String name = 'Threshold',
  bool deleted = false,
  bool shared = false,
}) => {
  'id': id,
  'kind': 'workout',
  'revision': 2,
  'deleted': deleted,
  'shared': shared,
  'payload': deleted
      ? <String, dynamic>{}
      : {
          'name': name,
          'blocks': [
            {'type': 'steady', 'duration_sec': 60, 'target_watts': 180},
          ],
        },
};

void main() {
  group('active synchronized plan validation', () {
    test(
      'accepts canonical active plans and preserves unknown payload fields',
      () {
        final catalog = Catalog.fromJson({
          'records': [envelope()],
        });
        final plan = catalog.upcoming(DateTime(2026, 9, 12)).single;

        expect(plan.record.id, planId);
        expect(plan.date, '2026-09-12');
        expect(plan.workoutId, workoutId);
        expect(plan.workoutName, 'Threshold');
        expect(plan.record.payload['future'], {
          'nested': [1, true, null],
        });
      },
    );

    test('accepts and compares every UUID spelling accepted by the server', () {
      for (final value in [
        planId.toUpperCase(),
        planId.replaceAll('-', ''),
        '{$planId}',
        'urn:uuid:$planId',
        '{{urn:uuid:urn:uuid:$planId}}',
        '}}urn:uuid:$planId{{',
      ]) {
        final raw = envelope(
          id: value,
          payload: {
            ...envelope()['payload'] as Map<String, dynamic>,
            'workout_id': value,
          },
        );
        final plan = Catalog.fromJson({
          'records': [raw],
        }).upcoming(DateTime(2026, 9, 12)).single;
        expect(sameUuid(plan.record.id, planId), isTrue);
        expect(sameUuid(plan.workoutId, planId), isTrue);
      }
      expect(
        canonicalUuid(List.filled(32, '١').join()),
        '11111111-1111-1111-1111-111111111111',
      );
    });

    test('rejects invalid ids, dates, names, and incompatible envelopes', () {
      final invalid = <Map<String, dynamic>>[
        envelope(id: 'not-a-uuid'),
        envelope(
          payload: {
            ...envelope()['payload'] as Map<String, dynamic>,
            'workout_id': 'not-a-uuid',
          },
        ),
        for (final date in [
          '2026-2-03',
          '2026-02-30',
          '2026-09-12T00:00:00',
          '0000-01-01',
        ])
          envelope(
            payload: {
              ...envelope()['payload'] as Map<String, dynamic>,
              'date': date,
            },
          ),
        envelope(
          payload: {
            ...envelope()['payload'] as Map<String, dynamic>,
            'workout_name': '   ',
          },
        ),
        envelope(
          payload: {
            ...envelope()['payload'] as Map<String, dynamic>,
            'workout_name': List.filled(201, 'x').join(),
          },
        ),
        envelope(revision: 0),
        envelope(shared: true),
      ];

      for (final record in invalid) {
        expect(
          () => Catalog.fromJson({
            'records': [record],
          }),
          throwsFormatException,
          reason: record.toString(),
        );
      }
    });

    test('keeps deleted tombstones opaque', () {
      final catalog = Catalog.fromJson({
        'records': [
          envelope(
            id: 'legacy-plan-id',
            revision: 0,
            deleted: true,
            shared: true,
            payload: {'future_tombstone': true},
          ),
        ],
      });

      expect(catalog.records.single.payload, {'future_tombstone': true});
      expect(catalog.upcoming(DateTime(2026, 1, 1)), isEmpty);
    });
  });

  group('PlanDraft', () {
    test('immutably preserves unknown fields while replacing owned values', () {
      final source = envelope()['payload'] as Map<String, dynamic>;
      final draft = PlanDraft.fromRecord(
        PlanRecord(SyncRecord.fromJson(envelope(payload: source))),
      );
      source['future'] = {'mutated': true};

      expect(
        () => (draft.extraFields['future'] as Map<String, dynamic>)['x'] = 1,
        throwsUnsupportedError,
      );

      final changed = draft
          .updateDate(DateTime(2026, 9, 13))
          .updateWorkout(
            WorkoutRecord(
              SyncRecord.fromJson(
                workoutEnvelope(otherWorkoutId, name: '  Endurance  '),
              ),
            ),
          );
      expect(draft.date, '2026-09-12');
      expect(draft.workoutId, workoutId);
      expect(changed.toJson(), {
        'future': {
          'nested': [1, true, null],
        },
        'date': '2026-09-13',
        'workout_id': otherWorkoutId,
        'workout_name': 'Endurance',
      });
    });

    test('refuses to serialize invalid draft values', () {
      for (final draft in [
        PlanDraft(
          date: '2026-02-30',
          workoutId: workoutId,
          workoutName: 'Threshold',
        ),
        PlanDraft(
          date: '2026-09-12',
          workoutId: 'not-a-uuid',
          workoutName: 'Threshold',
        ),
        PlanDraft(date: '2026-09-12', workoutId: workoutId, workoutName: ' '),
      ]) {
        expect(draft.toJson, throwsFormatException);
      }
    });

    test('formats date components without a UTC conversion at boundaries', () {
      final draft = PlanDraft(
        date: '2026-06-01',
        workoutId: workoutId,
        workoutName: 'Threshold',
      );

      expect(
        draft.updateDate(DateTime.utc(2026, 1, 1, 0, 5)).date,
        '2026-01-01',
      );
      expect(
        draft.updateDate(DateTime(2026, 12, 31, 23, 55)).date,
        '2026-12-31',
      );
    });

    test('only visible authoritative workouts are startable', () {
      final draft = PlanDraft.fromRecord(
        PlanRecord(SyncRecord.fromJson(envelope())),
      );
      Catalog catalogWith(List<Map<String, dynamic>> records) =>
          Catalog.fromJson({'records': records});

      expect(draft.isWorkoutStartable(catalogWith([])), isFalse);
      expect(
        draft.isWorkoutStartable(
          catalogWith([workoutEnvelope(workoutId, deleted: true)]),
        ),
        isFalse,
      );
      expect(
        draft.isWorkoutStartable(catalogWith([workoutEnvelope(workoutId)])),
        isTrue,
      );
      expect(
        draft.isWorkoutStartable(
          catalogWith([workoutEnvelope(workoutId, shared: true)]),
        ),
        isTrue,
      );
    });
  });
}
