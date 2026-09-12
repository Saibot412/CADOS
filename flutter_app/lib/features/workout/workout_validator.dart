import 'dart:convert';

import 'workout_draft.dart';

/// Validation shared by draft import and serialization.
abstract final class WorkoutValidator {
  static const int maxBlocks = 2000;
  static const int maxDurationSeconds = 24 * 60 * 60;
  static const int maxWatts = 32767;
  static const int maxPayloadBytes = 2000000;

  static void validateDraft(WorkoutDraft draft) {
    validatePayload(draft.toJson());
  }

  static void validatePayload(Map<String, dynamic> payload) {
    _validateJson(payload);

    final name = payload['name'];
    if (name is! String || name.trim().isEmpty) {
      _invalid('Workoutname fehlt.');
    }

    final blocks = payload['blocks'];
    if (blocks is! List || blocks.isEmpty || blocks.length > maxBlocks) {
      _invalid('Workout benötigt 1 bis 2000 Blöcke.');
    }

    var totalDuration = 0;
    for (final value in blocks) {
      if (value is! Map<String, dynamic>) {
        _invalid('Ungültiger Workoutblock.');
      }
      final block = value;
      final type = block['type'];
      if (type != 'steady' && type != 'ramp') {
        _invalid('Unbekannter Blocktyp.');
      }

      final duration = block['duration_sec'];
      if (duration is! int || duration <= 0) {
        _invalid('Ungültige Blockdauer.');
      }
      totalDuration += duration;

      if (block['label'] != null && block['label'] is! String) {
        _invalid('Ungültige Blockbezeichnung.');
      }
      if (block['target_cadence'] != null &&
          !_isPositiveInt(block['target_cadence'])) {
        _invalid('Ungültige Zielkadenz.');
      }

      for (final key in const ['target_watts', 'start_watts', 'end_watts']) {
        final watts = block[key];
        if (watts != null &&
            (!_isPositiveIntegralNumber(watts) || (watts as num) > maxWatts)) {
          _invalid('Ungültiger ganzzahliger Workoutwert.');
        }
      }
      for (final key in const [
        'target_pct_ftp',
        'start_pct_ftp',
        'end_pct_ftp',
      ]) {
        final fraction = block[key];
        if (fraction != null &&
            (fraction is! num || !fraction.isFinite || fraction <= 0)) {
          _invalid('Ungültiger FTP-Anteil.');
        }
      }

      if (type == 'steady') {
        if (block['target_pct_ftp'] == null && block['target_watts'] == null) {
          _invalid('Leistungsziel fehlt.');
        }
      } else if ((block['start_pct_ftp'] == null &&
              block['start_watts'] == null) ||
          (block['end_pct_ftp'] == null && block['end_watts'] == null)) {
        _invalid('Leistungsziel fehlt.');
      }
    }
    if (totalDuration > maxDurationSeconds) {
      _invalid('Workout dauert länger als 24 Stunden.');
    }

    final ftpReference = payload['ftp_reference'];
    if (ftpReference != null && !_isPositiveIntegralNumber(ftpReference)) {
      _invalid('Ungültiger ganzzahliger Workoutwert.');
    }
    final sortOrder = payload['sort_order'];
    if (sortOrder != null &&
        (sortOrder is! num ||
            !sortOrder.isFinite ||
            sortOrder.remainder(1) != 0)) {
      _invalid('Ungültige Sortierung.');
    }
    for (final key in const [
      'description',
      'author',
      'category',
      'best_for',
      'when_to_do',
      'skip_if',
      'source_name',
    ]) {
      if (payload[key] != null && payload[key] is! String) {
        _invalid('Ungültige Workout-Metadaten.');
      }
    }
  }

  static bool _isPositiveInt(Object? value) => value is int && value > 0;

  static bool _isPositiveIntegralNumber(Object? value) =>
      value is num && value.isFinite && value > 0 && value.remainder(1) == 0;

  static void _validateJson(Map<String, dynamic> payload) {
    try {
      if (utf8.encode(jsonEncode(payload)).length > maxPayloadBytes) {
        _invalid('Workout ist größer als 2 MB.');
      }
    } on JsonUnsupportedObjectError {
      _invalid('Ungültige Workout-Zahlen oder Metadaten.');
    }
  }

  static Never _invalid(String message) => throw FormatException(message);
}
