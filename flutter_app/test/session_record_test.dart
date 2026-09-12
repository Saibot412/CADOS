import 'package:cados_app/features/catalog/records.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> sessionRecord(
  Map<String, dynamic> payload, {
  bool deleted = false,
}) => {
  'id': 'session-1',
  'kind': 'session',
  'revision': 4,
  'deleted': deleted,
  'shared': false,
  'payload': payload,
  'server_extension': {'retained': true},
};

Map<String, dynamic> requiredSessionPayload() => {
  'status': 'completed',
  'workout_name': 'Threshold',
  'timestamp': '2026-09-11T09:45:00Z',
  'duration_sec': 3600,
};

Catalog catalogWith(Map<String, dynamic> record) => Catalog.fromJson({
  'records': [record],
});

void main() {
  test('parses complete synchronized session payload and exposes getters', () {
    final raw = sessionRecord({
      ...requiredSessionPayload(),
      'plan_id': 'plan-1',
      'started_at': '2026-09-11T08:44:30+00:00',
      'workout_elapsed_sec': 3590,
      'ftp_watts': 275,
      'workout_file_name': 'threshold.zwo',
      'workout_payload': {
        'name': 'Threshold',
        'blocks': [
          {'type': 'steady', 'duration_sec': 3600, 'target_watts': 260},
        ],
      },
      'trainer_source': 'bluetooth_ftms',
      'metrics': {
        'avg_watts': 251.5,
        'max_heart_rate': 181,
        'future_metric': {'retained': true},
      },
      'samples': [
        {
          'elapsed_sec': 1.0,
          'duration_sec': 1.0,
          'workout_elapsed_sec': 0.0,
          'watts': 250,
        },
      ],
      'ftp_test_result': {
        'old_ftp': 250,
        'method': '75_percent_best_continuous_minute',
        'eligible': true,
        'best_minute_watts': 367,
        'estimated_ftp': 275,
        'applied_at': '2026-09-11T10:00:00Z',
        'future_result_field': 'retained',
      },
      'future_payload_field': {'retained': true},
    });

    final session = catalogWith(raw).sessions.single;

    expect(session.planId, 'plan-1');
    expect(session.status, 'completed');
    expect(session.workoutName, 'Threshold');
    expect(session.timestamp, DateTime.utc(2026, 9, 11, 9, 45));
    expect(session.startedAt, DateTime.utc(2026, 9, 11, 8, 44, 30));
    expect(session.duration, 3600);
    expect(session.workoutElapsedSec, 3590);
    expect(session.ftpWatts, 275);
    expect(session.workoutFileName, 'threshold.zwo');
    expect(session.workoutPayload!['name'], 'Threshold');
    expect(session.trainerSource, 'bluetooth_ftms');
    expect(session.metrics!['avg_watts'], 251.5);
    expect(session.metrics!['future_metric'], {'retained': true});
    expect(session.samples, hasLength(1));
    expect(session.ftpTestResult!['estimated_ftp'], 275);
    expect(session.record.toJson(), raw);
  });

  test('legacy sessions keep optional getters nullable and do not throw', () {
    final session = catalogWith(sessionRecord(requiredSessionPayload()))
        .sessions
        .single;

    expect(session.planId, isNull);
    expect(session.startedAt, isNull);
    expect(session.workoutElapsedSec, isNull);
    expect(session.ftpWatts, isNull);
    expect(session.workoutFileName, isNull);
    expect(session.workoutPayload, isNull);
    expect(session.trainerSource, isNull);
    expect(session.metrics, isNull);
    expect(session.samples, isNull);
    expect(session.ftpTestResult, isNull);
  });

  test('rejects malformed values for present synchronized session fields', () {
    final malformedValues = <String, Object?>{
      'plan_id': 1,
      'status': false,
      'workout_name': 1,
      'timestamp': '2026-02-30T10:00:00Z',
      'started_at': 'not-a-date',
      'duration_sec': 1.5,
      'workout_elapsed_sec': '10',
      'ftp_watts': 250.0,
      'workout_file_name': 4,
      'workout_payload': <Object?>[],
      'trainer_source': 4,
      'metrics': <Object?>[],
      'samples': <String, Object?>{},
      'ftp_test_result': <Object?>[],
    };

    for (final entry in malformedValues.entries) {
      expect(
        () => catalogWith(
          sessionRecord({...requiredSessionPayload(), entry.key: entry.value}),
        ),
        throwsFormatException,
        reason: entry.key,
      );
    }
  });

  test(
    'rejects non-finite/non-numeric metrics and invalid FTP result shape',
    () {
      for (final metrics in [
        {'avg_watts': double.nan},
        {'normalized_power': double.infinity},
        {'avg_watts': '251'},
      ]) {
        expect(
          () => catalogWith(
            sessionRecord({...requiredSessionPayload(), 'metrics': metrics}),
          ),
          throwsFormatException,
        );
      }

      for (final result in [
        <String, dynamic>{
          'old_ftp': 250,
          'method': '75_percent_best_continuous_minute',
          'eligible': 'yes',
        },
        <String, dynamic>{
          'old_ftp': 250,
          'method': '75_percent_best_continuous_minute',
          'eligible': true,
          'best_minute_watts': 367,
        },
        <String, dynamic>{
          'old_ftp': 250,
          'method': '75_percent_best_continuous_minute',
          'eligible': false,
        },
        <String, dynamic>{
          'old_ftp': 250,
          'method': '75_percent_best_continuous_minute',
          'eligible': false,
          'reason': 'Insufficient data',
          'applied_at': 'not-a-date',
        },
      ]) {
        expect(
          () => catalogWith(
            sessionRecord({
              ...requiredSessionPayload(),
              'ftp_test_result': result,
            }),
          ),
          throwsFormatException,
        );
      }
    },
  );

  test(
    'opaque session tombstones remain accepted and preserve unknown fields',
    () {
      final raw = sessionRecord({
        'future_payload': {'retained': true},
      }, deleted: true);
      final catalog = catalogWith(raw);

      expect(catalog.sessions, isEmpty);
      expect(catalog.records.single.toJson(), raw);
    },
  );
}
