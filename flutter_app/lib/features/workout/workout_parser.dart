import 'dart:convert';

import 'workout.dart';

/// Intersection of server validation and Python WorkoutLoader, without defaults
/// for account FTP. Original metadata is retained separately by the session.
abstract final class WorkoutParser {
  static Workout parse(Map<String, dynamic> payload, {required int ftp}) {
    if (ftp < 30 || ftp > 2000) _invalid('Profil-FTP fehlt oder ist ungültig.');
    validate(payload);
    final raw = payload['blocks'] as List;
    return Workout((payload['name'] as String).trim(), [
      for (var i = 0; i < raw.length; i++)
        _block(raw[i] as Map<String, dynamic>, i),
    ], ftp: ftp);
  }

  static void validate(Map<String, dynamic> p) {
    try {
      if (utf8.encode(jsonEncode(p)).length > 2000000) {
        _invalid('Workout ist größer als 2 MB.');
      }
    } on JsonUnsupportedObjectError {
      _invalid('Ungültige Workout-Zahlen.');
    }
    if (p['name'] is! String || (p['name'] as String).trim().isEmpty) {
      _invalid('Workoutname fehlt.');
    }
    final blocks = p['blocks'];
    if (blocks is! List || blocks.isEmpty || blocks.length > 2000) {
      _invalid('Workout benötigt 1 bis 2000 Blöcke.');
    }
    var duration = 0;
    for (var i = 0; i < blocks.length; i++) {
      if (blocks[i] is! Map<String, dynamic>) {
        _invalid('Ungültiger Workoutblock.');
      }
      final b = _block(blocks[i] as Map<String, dynamic>, i);
      duration += b.duration;
    }
    if (duration > 86400) _invalid('Workout dauert länger als 24 Stunden.');
    _integer(p, 'ftp_reference');
    if (p['sort_order'] != null &&
        (p['sort_order'] is! num ||
            !(p['sort_order'] as num).isFinite ||
            (p['sort_order'] as num) % 1 != 0)) {
      _invalid('Ungültige Sortierung.');
    }
    for (final key in [
      'description',
      'author',
      'category',
      'best_for',
      'when_to_do',
      'skip_if',
      'source_name',
    ]) {
      if (p[key] != null && p[key] is! String) {
        _invalid('Ungültige Workout-Metadaten.');
      }
    }
  }

  static WorkoutBlock _block(Map<String, dynamic> b, int index) {
    final kind = b['type'];
    if (kind != 'steady' && kind != 'ramp') _invalid('Unbekannter Blocktyp.');
    if (b['duration_sec'] is! int || (b['duration_sec'] as int) <= 0) {
      _invalid('Ungültige Blockdauer.');
    }
    if (b['target_cadence'] != null && b['target_cadence'] is! int) {
      _invalid('Ungültige Zielkadenz.');
    }
    final cadence = _integer(b, 'target_cadence');
    if (b['label'] != null && b['label'] is! String) {
      _invalid('Ungültige Blockbezeichnung.');
    }
    final target = _integer(b, 'target_watts'),
        start = _integer(b, 'start_watts'),
        end = _integer(b, 'end_watts');
    final pct = _fraction(b, 'target_pct_ftp'),
        startPct = _fraction(b, 'start_pct_ftp'),
        endPct = _fraction(b, 'end_pct_ftp');
    if (kind == 'steady' && target == null && pct == null ||
        kind == 'ramp' &&
            ((start == null && startPct == null) ||
                (end == null && endPct == null))) {
      _invalid('Leistungsziel fehlt.');
    }
    return WorkoutBlock(
      kind: kind == 'steady' ? BlockKind.steady : BlockKind.ramp,
      label: (b['label'] as String?)?.isNotEmpty == true
          ? b['label'] as String
          : 'Block ${index + 1}',
      duration: b['duration_sec'] as int,
      cadence: cadence,
      targetWatts: target,
      targetPct: pct,
      startWatts: start,
      endWatts: end,
      startPct: startPct,
      endPct: endPct,
    );
  }

  static int? _integer(Map<String, dynamic> b, String key) {
    final v = b[key];
    if (v == null) return null;
    if (v is! num ||
        !v.isFinite ||
        v % 1 != 0 ||
        v <= 0 ||
        key.endsWith('watts') && v > 32767) {
      _invalid('Ungültiger ganzzahliger Workoutwert.');
    }
    return v.toInt();
  }

  static double? _fraction(Map<String, dynamic> b, String key) {
    final v = b[key];
    if (v == null) return null;
    if (v is! num || !v.isFinite || v <= 0) _invalid('Ungültiger FTP-Anteil.');
    return v.toDouble();
  }

  static Never _invalid(String message) => throw FormatException(message);
}
