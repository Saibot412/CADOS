import 'dart:convert';
import 'dart:math';

import '../workout/workout.dart';
import '../workout/workout_parser.dart';

String sessionUuid() {
  final random = Random.secure();
  final bytes = List.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final h = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
}

Map<String, dynamic> copyJson(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;

/// Journal metadata is local only. `payload` below matches WorkoutSessionRecord.
class SessionData {
  SessionData({
    required this.id,
    required this.server,
    required this.accountId,
    required this.workoutId,
    required this.workoutPayload,
    required this.profile,
    required this.ftp,
    required this.startedAt,
    this.planId,
  });
  final String id, server, accountId, workoutId, startedAt;
  final String? planId;
  final Map<String, dynamic> workoutPayload, profile;
  final int ftp;
  double elapsed = 0, activeSeconds = 0;
  int adjustment = 0, segment = 0;
  final List<Map<String, dynamic>> samples = [];
  int _sampleBytes = 0;
  static const maxSampleBytes = 16 * 1024 * 1024;
  Map<String, dynamic> draft() => {
    'version': 1,
    'session_id': id,
    'server': server,
    'account_id': accountId,
    'workout_id': workoutId,
    'workout': workoutPayload,
    'profile': profile,
    'ftp_watts': ftp,
    'elapsed_sec': elapsed,
    'active_seconds': activeSeconds,
    'started_at': startedAt,
    'adjustment_watts': adjustment,
    'segment': segment,
    'plan_id': planId,
    'samples': samples,
  };
  static SessionData restore(Map<String, dynamic> j) {
    try {
      if (j['version'] != 1) throw const FormatException();
      final data = SessionData(
        id: j['session_id'] as String,
        server: j['server'] as String,
        accountId: j['account_id'] as String,
        workoutId: j['workout_id'] as String,
        workoutPayload: copyJson(j['workout'] as Map<String, dynamic>),
        profile: copyJson(j['profile'] as Map<String, dynamic>),
        ftp: j['ftp_watts'] as int,
        startedAt: j['started_at'] as String,
        planId: j['plan_id'] as String?,
      );
      final workout = WorkoutParser.parse(data.workoutPayload, ftp: data.ftp);
      data.elapsed = (j['elapsed_sec'] as num).toDouble();
      data.activeSeconds = (j['active_seconds'] as num).toDouble();
      data.adjustment = j['adjustment_watts'] as int;
      data.segment = j['segment'] as int;
      if (!RegExp(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
          ).hasMatch(data.id) ||
          data.profile['id'] is! String ||
          data.profile['name'] is! String ||
          DateTime.tryParse(data.startedAt) == null ||
          !data.elapsed.isFinite ||
          data.elapsed < 0 ||
          data.elapsed > workout.duration ||
          !data.activeSeconds.isFinite ||
          data.activeSeconds < 0 ||
          data.activeSeconds > 86400 ||
          data.segment < 0) {
        throw const FormatException();
      }
      final samples = j['samples'] as List;
      if (samples.length > 86401) throw const FormatException();
      var sum = 0.0;
      for (final raw in samples) {
        final s = Map<String, dynamic>.from(raw as Map);
        for (final key in [
          'elapsed_sec',
          'duration_sec',
          'workout_elapsed_sec',
          'watts',
          'target_watts',
          'segment',
        ]) {
          if (s[key] is! num ||
              !(s[key] as num).isFinite ||
              (s[key] as num) < 0) {
            throw const FormatException();
          }
        }
        if ((s['duration_sec'] as num) <= 0 || (s['duration_sec'] as num) > 5) {
          throw const FormatException();
        }
        for (final key in ['cadence', 'heart_rate']) {
          if (s[key] != null &&
              (s[key] is! num ||
                  !(s[key] as num).isFinite ||
                  (s[key] as num) < 0)) {
            throw const FormatException();
          }
        }
        sum += (s['duration_sec'] as num).toDouble();
        if (((s['elapsed_sec'] as num) - sum).abs() > .001 ||
            (s['workout_elapsed_sec'] as num) + (s['duration_sec'] as num) >
                workout.duration + .001) {
          throw const FormatException();
        }
        data._sampleBytes += utf8.encode(jsonEncode(s)).length + 1;
        if (data._sampleBytes > maxSampleBytes) throw const FormatException();
        data.samples.add(s);
      }
      if ((sum - data.activeSeconds).abs() > .001) {
        throw const FormatException();
      }
      return data;
    } catch (_) {
      throw const FormatException(
        'Trainingssicherung ist beschädigt. Datei bleibt erhalten.',
      );
    }
  }

  void sample({
    required double duration,
    required double from,
    required int watts,
    required num? cadence,
    required int? hr,
    required int target,
    required int block,
  }) {
    if (samples.length >= 86401) {
      throw const FormatException('Maximale Anzahl Messwerte erreicht.');
    }
    double rounded(num value) => (value * 1000000).round() / 1000000;
    final sample = <String, dynamic>{
      'segment': segment,
      'elapsed_sec': rounded(activeSeconds + duration),
      'duration_sec': rounded(duration),
      'workout_elapsed_sec': rounded(from),
      'watts': watts,
      'cadence': cadence,
      'heart_rate': hr,
      'target_watts': target,
      'block_index': block,
    };
    final bytes = utf8.encode(jsonEncode(sample)).length + 1;
    if (_sampleBytes + bytes > maxSampleBytes) {
      throw const FormatException(
        'Messwertspeicher voll. Bitte Einheit beenden und synchronisieren.',
      );
    }
    _sampleBytes += bytes;
    activeSeconds += duration;
    samples.add(sample);
  }

  Map<String, dynamic> finalize(String status, DateTime at) => {
    'server': server,
    'account_id': accountId,
    'record': {
      'id': id,
      'kind': 'session',
      'revision': 0,
      'shared': false,
      'deleted': false,
      'payload': {
        'id': id,
        'user_id': profile['id'],
        'user_name': profile['name'],
        'workout_name': workoutPayload['name'],
        'workout_file_name': workoutPayload['source_name'],
        'workout_payload': workoutPayload,
        'duration_sec': pythonRound(activeSeconds),
        'workout_elapsed_sec': pythonRound(elapsed),
        'ftp_watts': ftp,
        'started_at': startedAt,
        'timestamp': at.toUtc().toIso8601String(),
        'status': status,
        'trainer_source': 'bluetooth_ftms',
        'plan_id': planId,
        'perceived_exertion': null,
        'ftp_test_result': null,
        'metrics': <String, dynamic>{},
        'samples': samples,
      },
    },
  };
}
