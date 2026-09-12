import 'package:cados_app/core/uuid_v4.dart';
import 'package:cados_app/features/workout/workout_draft.dart';
import 'package:cados_app/features/workout/workout_validator.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('new workout ids are unique RFC 4122 version 4 UUIDs', () {
    final ids = List.generate(100, (_) => newUuidV4());
    final pattern = RegExp(
      r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    );
    expect(ids.toSet(), hasLength(ids.length));
    expect(ids.every(pattern.hasMatch), isTrue);
  });

  group('WorkoutDraft conversion', () {
    test('round-trips metadata, unknown block fields, and dormant watts', () {
      final payload = <String, dynamic>{
        'name': ' Threshold ',
        'description': 'Mixed targets',
        'future_metadata': {
          'nested': [
            1,
            {'enabled': true},
          ],
        },
        'blocks': [
          {
            'type': 'steady',
            'duration_sec': 300,
            'label': 'Work',
            'target_pct_ftp': 0.95,
            'target_watts': 275,
            'target_cadence': 92,
            'future_block': {'colour': 'red'},
          },
          {
            'type': 'ramp',
            'duration_sec': 120,
            'start_pct_ftp': 0.5,
            'start_watts': 140,
            'end_pct_ftp': 1.1,
            'end_watts': 310,
            'extension': [1, 2, 3],
          },
        ],
      };

      final draft = WorkoutDraft.fromJson(payload);
      final steady = draft.blocks.first as SteadyBlockDraft;
      final ramp = draft.blocks.last as RampBlockDraft;

      expect(steady.targetPctFtp, 0.95);
      expect(steady.targetWatts, 275);
      expect(steady.usesFtpTarget, isTrue);
      expect(ramp.startWatts, 140);
      expect(ramp.endWatts, 310);
      expect(ramp.usesFtpStart, isTrue);
      expect(ramp.usesFtpEnd, isTrue);
      expect(draft.toJson(), payload);
    });

    test('takes defensive copies at input and output boundaries', () {
      final metadata = <String, dynamic>{
        'nested': <dynamic>[1],
      };
      final extras = <String, dynamic>{
        'nested': <String, dynamic>{'value': 1},
      };
      final draft = WorkoutDraft(
        name: 'Safe',
        metadata: metadata,
        blocks: [
          SteadyBlockDraft(
            durationSec: 60,
            targetWatts: 100,
            extraFields: extras,
          ),
        ],
      );
      metadata['nested'] = [2];
      (extras['nested'] as Map<String, dynamic>)['value'] = 2;

      final firstJson = draft.toJson();
      (firstJson['nested'] as List<dynamic>).add(3);
      ((firstJson['blocks'] as List<dynamic>).first['nested']
              as Map<String, dynamic>)['value'] =
          3;

      final secondJson = draft.toJson();
      expect(secondJson['nested'], [1]);
      expect(
        ((secondJson['blocks'] as List<dynamic>).first['nested']
            as Map<String, dynamic>)['value'],
        1,
      );
      expect(
        () => draft.blocks.add(draft.blocks.first),
        throwsUnsupportedError,
      );
    });
  });

  group('WorkoutDraft editing', () {
    final a = SteadyBlockDraft(durationSec: 10, targetWatts: 100);
    final b = RampBlockDraft(durationSec: 20, startWatts: 100, endWatts: 200);
    final c = SteadyBlockDraft(durationSec: 30, targetPctFtp: 0.8);

    test('add, remove, reorder, and update return independent drafts', () {
      final original = WorkoutDraft(name: 'Edit', blocks: [a, b]);
      final added = original.addBlock(c);
      final inserted = original.addBlock(c, index: 1);
      final removed = added.removeBlock(1);
      final moved = added.reorderBlock(2, 0);
      final updated = original.updateBlock(0, a.copyWith(durationSec: 15));

      expect(original.blocks, [a, b]);
      expect(added.blocks, [a, b, c]);
      expect(inserted.blocks, [a, c, b]);
      expect(removed.blocks, [a, c]);
      expect(moved.blocks, [c, a, b]);
      expect(updated.blocks.first.durationSec, 15);
      expect(original.blocks.first.durationSec, 10);
    });

    test('copyWith can clear optional known fields without losing extras', () {
      final steady = SteadyBlockDraft(
        durationSec: 10,
        targetPctFtp: 0.5,
        targetWatts: 123,
        targetCadence: 90,
        extraFields: {'extension': true},
      );
      final changed = steady.copyWith(targetPctFtp: null, targetCadence: null);

      expect(changed.targetPctFtp, isNull);
      expect(changed.targetCadence, isNull);
      expect(changed.targetWatts, 123);
      expect(changed.extraFields, {'extension': true});
    });
  });

  group('WorkoutValidator', () {
    test('accepts exact block count, duration, and numeric boundaries', () {
      final blocks = List<WorkoutBlockDraft>.generate(
        2000,
        (_) => SteadyBlockDraft(durationSec: 1, targetWatts: 32767),
      );
      final draft = WorkoutDraft(name: 'Limits', blocks: blocks).copyWith(
        blocks: [SteadyBlockDraft(durationSec: 86400, targetPctFtp: 0.0001)],
      );

      expect(() => WorkoutValidator.validateDraft(draft), returnsNormally);
      expect(
        () => WorkoutDraft(name: 'Count', blocks: blocks).toJson(),
        returnsNormally,
      );
    });

    test('rejects invalid names, block counts, and total duration', () {
      expect(
        () => WorkoutDraft(
          name: ' ',
          blocks: [SteadyBlockDraft(durationSec: 1, targetWatts: 1)],
        ).toJson(),
        throwsFormatException,
      );
      expect(
        () => WorkoutDraft(name: 'Empty', blocks: const []).toJson(),
        throwsFormatException,
      );
      expect(
        () => WorkoutDraft(
          name: 'Too many',
          blocks: List.generate(
            2001,
            (_) => SteadyBlockDraft(durationSec: 1, targetWatts: 1),
          ),
        ).toJson(),
        throwsFormatException,
      );
      expect(
        () => WorkoutDraft(
          name: 'Too long',
          blocks: [SteadyBlockDraft(durationSec: 86401, targetWatts: 1)],
        ).toJson(),
        throwsFormatException,
      );
    });

    test(
      'rejects non-positive or non-integer duration and cadence payloads',
      () {
        for (final block in [
          {'type': 'steady', 'duration_sec': 0, 'target_watts': 100},
          {'type': 'steady', 'duration_sec': 1.5, 'target_watts': 100},
          {
            'type': 'steady',
            'duration_sec': 1,
            'target_watts': 100,
            'target_cadence': 0,
          },
          {
            'type': 'steady',
            'duration_sec': 1,
            'target_watts': 100,
            'target_cadence': 90.0,
          },
        ]) {
          expect(
            () => WorkoutDraft.fromJson({
              'name': 'Invalid',
              'blocks': [block],
            }),
            throwsFormatException,
          );
        }
      },
    );

    test('validates every present target even when FTP takes precedence', () {
      for (final target in [0, 1.5, 32768, double.infinity]) {
        expect(
          () => WorkoutDraft.fromJson({
            'name': 'Invalid watts',
            'blocks': [
              {
                'type': 'steady',
                'duration_sec': 1,
                'target_pct_ftp': 0.8,
                'target_watts': target,
              },
            ],
          }),
          throwsFormatException,
        );
      }
      for (final fraction in [0, -0.1, double.nan, double.infinity]) {
        expect(
          () => WorkoutDraft.fromJson({
            'name': 'Invalid fraction',
            'blocks': [
              {'type': 'steady', 'duration_sec': 1, 'target_pct_ftp': fraction},
            ],
          }),
          throwsFormatException,
        );
      }
    });

    test('requires the appropriate steady and ramp targets', () {
      for (final block in [
        {'type': 'steady', 'duration_sec': 1},
        {'type': 'ramp', 'duration_sec': 1, 'start_watts': 100},
        {'type': 'ramp', 'duration_sec': 1, 'end_pct_ftp': 0.8},
      ]) {
        expect(
          () => WorkoutDraft.fromJson({
            'name': 'Missing',
            'blocks': [block],
          }),
          throwsFormatException,
        );
      }
    });

    test('rejects invalid known metadata and non-JSON unknown fields', () {
      expect(
        () => WorkoutDraft.fromJson({
          'name': 'Metadata',
          'description': 42,
          'blocks': [
            {'type': 'steady', 'duration_sec': 1, 'target_watts': 1},
          ],
        }),
        throwsFormatException,
      );
      expect(
        () => WorkoutDraft(
          name: 'Unknown',
          metadata: {'unknown': Object()},
          blocks: [SteadyBlockDraft(durationSec: 1, targetWatts: 1)],
        ).toJson(),
        throwsFormatException,
      );
    });
  });
}
