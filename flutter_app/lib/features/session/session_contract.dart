import 'dart:convert';

import '../workout/workout_parser.dart';

/// Validate our outgoing WorkoutSessionRecord before persistence/upload. Server
/// derived metrics and FTP-test results remain the server's responsibility.
void validateSessionEntry(Map<String, dynamic> entry) {
  try {
    final r = entry['record'] as Map<String, dynamic>;
    final p = r['payload'] as Map<String, dynamic>;
    final uuid = RegExp(
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    );
    if (entry['server'] is! String ||
        entry['account_id'] is! String ||
        r['id'] is! String ||
        !uuid.hasMatch(r['id'] as String) ||
        r['id'] != p['id'] ||
        r['kind'] != 'session' ||
        r['revision'] != 0 ||
        r['shared'] != false ||
        r['deleted'] != false) {
      throw const FormatException();
    }
    for (final key in [
      'user_id',
      'user_name',
      'workout_name',
      'trainer_source',
      'started_at',
      'timestamp',
    ]) {
      if (p[key] is! String || (p[key] as String).isEmpty) {
        throw const FormatException();
      }
    }
    if (p['plan_id'] != null &&
        (p['plan_id'] is! String || !uuid.hasMatch(p['plan_id'] as String))) {
      throw const FormatException();
    }
    if (!['completed', 'stopped'].contains(p['status']) ||
        DateTime.tryParse(p['started_at'] as String) == null ||
        DateTime.tryParse(p['timestamp'] as String) == null) {
      throw const FormatException();
    }
    final workout = WorkoutParser.parse(
      p['workout_payload'] as Map<String, dynamic>,
      ftp: p['ftp_watts'] as int,
    );
    if (p['duration_sec'] is! int ||
        (p['duration_sec'] as int) < 0 ||
        (p['duration_sec'] as int) > 86400 ||
        p['workout_elapsed_sec'] is! int ||
        (p['workout_elapsed_sec'] as int) < 0 ||
        (p['workout_elapsed_sec'] as int) > workout.duration ||
        p['metrics'] is! Map<String, dynamic>) {
      throw const FormatException();
    }
    final samples = p['samples'] as List;
    if (samples.length > 86401) throw const FormatException();
    var sum = 0.0, previousEnd = 0.0;
    for (final sample in samples) {
      final s = sample as Map<String, dynamic>;
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
      final dt = (s['duration_sec'] as num).toDouble();
      final elapsed = (s['workout_elapsed_sec'] as num).toDouble();
      if (dt <= 0 ||
          dt > 5 ||
          elapsed < previousEnd - .001 ||
          elapsed + dt > workout.duration + .001 ||
          (s['target_watts'] as num) > 32767) {
        throw const FormatException();
      }
      previousEnd = elapsed + dt;
      sum += dt;
      if (((s['elapsed_sec'] as num) - sum).abs() > .001) {
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
    }
    if ((sum - (p['duration_sec'] as int)).abs() > .501 ||
        utf8
                .encode(
                  jsonEncode({
                    'changes': [r],
                  }),
                )
                .length >
            20000000) {
      throw const FormatException();
    }
  } catch (_) {
    throw const FormatException(
      'Session-Daten ungültig oder zu groß. Lokale Daten bleiben erhalten.',
    );
  }
}
