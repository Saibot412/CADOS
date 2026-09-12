import '../../core/json_value.dart';

/// The server snapshot is authoritative, including tombstones and shared records.
/// Keep the entire envelope/payload so future writes cannot discard extensions.
class SyncRecord {
  factory SyncRecord.fromJson(Map<String, dynamic> json) {
    try {
      final record = SyncRecord._parse(
        freezeJson(json) as Map<String, dynamic>,
      );
      if (record.id.isEmpty || record.revision < 0) {
        throw const FormatException();
      }
      return record;
    } catch (_) {
      throw const FormatException('Ungültiger Sync-Datensatz.');
    }
  }
  SyncRecord._parse(Map<String, dynamic> json)
    : raw = Map.unmodifiable(json),
      id = json['id'] as String,
      kind = json['kind'] as String,
      revision = json['revision'] as int,
      deleted = json['deleted'] as bool,
      shared = json['shared'] as bool,
      payload = Map.unmodifiable(json['payload'] as Map<String, dynamic>);
  final Map<String, dynamic> raw, payload;
  final String id, kind;
  final int revision;
  final bool deleted, shared;
  Map<String, dynamic> toJson() => Map.of(raw);
}

class ProfileRecord {
  ProfileRecord(this.record);
  final SyncRecord record;
  String get name => record.payload['name'] as String;
  int? get ftp => record.payload['ftp'] as int?;
  num? get weightKg => record.payload['weight_kg'] as num?;
  int? get maxHr => record.payload['max_hr'] as int?;
}

class WorkoutRecord {
  WorkoutRecord(this.record);
  final SyncRecord record;
  String get name => record.payload['name'] as String;
  String? get description => record.payload['description'] as String?;
  String? get category => record.payload['category'] as String?;
  List<WorkoutBlockRecord> get blocks => (record.payload['blocks'] as List)
      .map((b) => WorkoutBlockRecord(Map<String, dynamic>.from(b as Map)))
      .toList();
  int get duration => blocks.fold(0, (sum, b) => sum + b.duration);
}

class WorkoutBlockRecord {
  WorkoutBlockRecord(this.raw);
  final Map<String, dynamic> raw;
  String get type => raw['type'] as String;
  int get duration => raw['duration_sec'] as int;
  num? get targetWatts => raw['target_watts'] as num?;
  num? get targetPctFtp => raw['target_pct_ftp'] as num?;
  num? get startWatts => raw['start_watts'] as num?;
  num? get endWatts => raw['end_watts'] as num?;
  num? get startPctFtp => raw['start_pct_ftp'] as num?;
  num? get endPctFtp => raw['end_pct_ftp'] as num?;
  int? get cadence => raw['target_cadence'] as int?;
}

class PlanRecord {
  PlanRecord(this.record) {
    if (record.kind != 'plan' ||
        record.deleted ||
        record.shared ||
        !isValidUuid(record.id)) {
      throw const FormatException('Invalid plan envelope.');
    }
    validatePayload(record.payload);
  }

  static void validatePayload(Map<String, dynamic> payload) {
    final date = payload['date'];
    final workoutId = payload['workout_id'];
    final workoutName = payload['workout_name'];
    if (!isLocalCalendarDate(date) ||
        workoutId is! String ||
        !isValidUuid(workoutId) ||
        workoutName is! String ||
        workoutName.trim().isEmpty ||
        workoutName.length > 200) {
      throw const FormatException('Invalid plan payload.');
    }
  }

  final SyncRecord record;
  String get date => record.payload['date'] as String;
  String get workoutId => record.payload['workout_id'] as String;
  String get workoutName => record.payload['workout_name'] as String;
}

final RegExp _uuidHex = RegExp(r'^[0-9a-f]{32}$');
const _decimalZeros = <int>[
  0x30,
  0x660,
  0x6F0,
  0x7C0,
  0x966,
  0x9E6,
  0xA66,
  0xAE6,
  0xB66,
  0xBE6,
  0xC66,
  0xCE6,
  0xD66,
  0xDE6,
  0xE50,
  0xED0,
  0xF20,
  0x1040,
  0x1090,
  0x17E0,
  0x1810,
  0x1946,
  0x19D0,
  0x1A80,
  0x1A90,
  0x1B50,
  0x1BB0,
  0x1C40,
  0x1C50,
  0xA620,
  0xA8D0,
  0xA900,
  0xA9D0,
  0xA9F0,
  0xAA50,
  0xABF0,
  0xFF10,
  0x104A0,
  0x10D30,
  0x11066,
  0x110F0,
  0x11136,
  0x111D0,
  0x112F0,
  0x11450,
  0x114D0,
  0x11650,
  0x116C0,
  0x11730,
  0x118E0,
  0x11950,
  0x11C50,
  0x11D50,
  0x11DA0,
  0x16A60,
  0x16AC0,
  0x16B50,
  0x1D7CE,
  0x1D7D8,
  0x1D7E2,
  0x1D7EC,
  0x1D7F6,
  0x1E140,
  0x1E2F0,
  0x1E950,
  0x1FBF0,
];

/// Mirrors Python's UUID(string) forms so one server-valid record cannot make
/// the complete authoritative snapshot unreadable.
String? normalizedUuid(String value) {
  final candidate = value
      .replaceAll('urn:', '')
      .replaceAll('uuid:', '')
      .replaceFirst(RegExp(r'^[{}]+'), '')
      .replaceFirst(RegExp(r'[{}]+$'), '')
      .replaceAll('-', '');
  final ascii = StringBuffer();
  for (final rune in candidate.runes) {
    if (rune >= 0x30 && rune <= 0x39 ||
        rune >= 0x41 && rune <= 0x46 ||
        rune >= 0x61 && rune <= 0x66) {
      ascii.writeCharCode(rune >= 0x41 && rune <= 0x46 ? rune + 0x20 : rune);
      continue;
    }
    int? digit;
    for (final zero in _decimalZeros) {
      if (rune >= zero && rune <= zero + 9) {
        digit = rune - zero;
        break;
      }
    }
    if (digit == null) return null;
    ascii.write(digit);
  }
  final normalized = ascii.toString();
  return _uuidHex.hasMatch(normalized) ? normalized : null;
}

bool isValidUuid(String value) => normalizedUuid(value) != null;

String? canonicalUuid(String value) {
  final hex = normalizedUuid(value);
  if (hex == null) return null;
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
      '${hex.substring(12, 16)}-${hex.substring(16, 20)}-'
      '${hex.substring(20)}';
}

bool sameUuid(String left, String right) {
  final normalizedLeft = normalizedUuid(left);
  return normalizedLeft != null && normalizedLeft == normalizedUuid(right);
}

bool isLocalCalendarDate(Object? value) {
  if (value is! String) return false;
  final match = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(value);
  if (match == null) return false;
  final year = int.parse(match.group(1)!);
  final month = int.parse(match.group(2)!);
  final day = int.parse(match.group(3)!);
  if (year == 0) return false;
  final parsed = DateTime.utc(year, month, day);
  return parsed.year == year && parsed.month == month && parsed.day == day;
}

class SessionRecord {
  SessionRecord(this.record);
  final SyncRecord record;
  String? get planId => record.payload['plan_id'] as String?;
  String get status => record.payload['status'] as String;
  String get workoutName => record.payload['workout_name'] as String;
  DateTime get timestamp =>
      DateTime.parse(record.payload['timestamp'] as String);
  DateTime? get startedAt => _optionalDateTime('started_at');
  int get duration => record.payload['duration_sec'] as int;
  int? get workoutElapsedSec => record.payload['workout_elapsed_sec'] as int?;
  int? get ftpWatts => record.payload['ftp_watts'] as int?;
  String? get workoutFileName => record.payload['workout_file_name'] as String?;
  Map<String, dynamic>? get workoutPayload =>
      record.payload['workout_payload'] as Map<String, dynamic>?;
  String? get trainerSource => record.payload['trainer_source'] as String?;
  Map<String, dynamic>? get metrics =>
      record.payload['metrics'] as Map<String, dynamic>?;
  List<dynamic>? get samples => record.payload['samples'] as List?;
  Map<String, dynamic>? get ftpTestResult =>
      record.payload['ftp_test_result'] as Map<String, dynamic>?;

  DateTime? _optionalDateTime(String key) {
    final value = record.payload[key] as String?;
    return value == null ? null : DateTime.parse(value);
  }
}

bool _isValidDateTime(Object? value) {
  if (value is! String || DateTime.tryParse(value) == null) return false;
  final match = RegExp(r'^(\d{4})-(\d{2})-(\d{2})').firstMatch(value);
  if (match == null) return false;
  final year = int.parse(match.group(1)!);
  final month = int.parse(match.group(2)!);
  final day = int.parse(match.group(3)!);
  final calendarDate = DateTime.utc(year, month, day);
  return calendarDate.year == year &&
      calendarDate.month == month &&
      calendarDate.day == day;
}

void _validateSessionPayload(Map<String, dynamic> payload) {
  void optionalField<T>(String key) {
    final value = payload[key];
    if (value != null && value is! T) {
      throw const FormatException('Invalid session field.');
    }
  }

  for (final key in ['plan_id', 'workout_file_name', 'trainer_source']) {
    optionalField<String>(key);
  }
  optionalField<int>('workout_elapsed_sec');
  optionalField<int>('ftp_watts');
  optionalField<Map<String, dynamic>>('workout_payload');
  optionalField<Map<String, dynamic>>('metrics');
  optionalField<List>('samples');
  optionalField<Map<String, dynamic>>('ftp_test_result');

  if (!_isValidDateTime(payload['timestamp']) ||
      payload['started_at'] != null &&
          !_isValidDateTime(payload['started_at'])) {
    throw const FormatException('Invalid session timestamp.');
  }
  final duration = payload['duration_sec'] as int;
  final workoutElapsed = payload['workout_elapsed_sec'] as int?;
  final ftp = payload['ftp_watts'] as int?;
  if (duration < 0 ||
      duration > 86400 ||
      workoutElapsed != null && workoutElapsed < 0 ||
      ftp != null && (ftp < 30 || ftp > 2000)) {
    throw const FormatException('Invalid session number.');
  }

  final metrics = payload['metrics'] as Map<String, dynamic>?;
  if (metrics != null) {
    const numericMetricFields = [
      'max_watts',
      'avg_watts',
      'max_cadence',
      'avg_cadence',
      'max_heart_rate',
      'avg_heart_rate',
      'best_minute_watts',
      'work_kj',
      'normalized_power',
      'intensity_factor',
      'tss',
      'calories',
    ];
    for (final key in numericMetricFields) {
      final value = metrics[key];
      if (value != null && (value is! num || !value.isFinite)) {
        throw const FormatException('Invalid session metrics.');
      }
    }
  }

  final samples = payload['samples'] as List?;
  if (samples != null) {
    const numericFields = [
      'elapsed_sec',
      'duration_sec',
      'workout_elapsed_sec',
      'watts',
      'target_watts',
      'cadence',
      'heart_rate',
      'segment',
      'block_index',
    ];
    for (final sample in samples) {
      if (sample is! Map<String, dynamic>) {
        throw const FormatException('Invalid session sample.');
      }
      for (final key in numericFields) {
        final value = sample[key];
        if (value != null && (value is! num || !value.isFinite)) {
          throw const FormatException('Invalid session sample number.');
        }
      }
    }
  }

  final result = payload['ftp_test_result'] as Map<String, dynamic>?;
  if (result == null) return;
  final oldFtp = result['old_ftp'];
  final method = result['method'];
  final eligible = result['eligible'];
  if (!result.containsKey('old_ftp') ||
      oldFtp != null && oldFtp is! int ||
      method is! String ||
      method.isEmpty ||
      eligible is! bool) {
    throw const FormatException('Invalid FTP test result.');
  }
  if (eligible) {
    if (result['best_minute_watts'] is! int ||
        result['estimated_ftp'] is! int) {
      throw const FormatException('Invalid FTP test result.');
    }
  } else if (result['reason'] is! String ||
      (result['reason'] as String).isEmpty) {
    throw const FormatException('Invalid FTP test result.');
  }
  if (result['applied_at'] != null && !_isValidDateTime(result['applied_at'])) {
    throw const FormatException('Invalid FTP test result timestamp.');
  }
}

class Catalog {
  factory Catalog.fromJson(Map<String, dynamic> json) {
    try {
      return Catalog._parse(json);
    } catch (_) {
      throw const FormatException('Ungültige Kontodaten vom Server.');
    }
  }
  Catalog._parse(Map<String, dynamic> json)
    : records = List.unmodifiable(
        (json['records'] as List).map(
          (r) => SyncRecord.fromJson(r as Map<String, dynamic>),
        ),
      ) {
    // Validate fields used by presentation before publishing a snapshot. A bad
    // response becomes an account error, never an exception during widget build.
    if (records.map((r) => r.id).toSet().length != records.length) {
      throw const FormatException('Doppelte Datensatz-ID.');
    }
    for (final r in records.where((r) => !r.deleted)) {
      final p = r.payload;
      void requiredField<T>(String key) {
        if (p[key] is! T) throw const FormatException('Invalid sync record.');
      }

      switch (r.kind) {
        case 'profile':
          requiredField<String>('name');
          final profileName = p['name'] as String;
          final ftp = p['ftp'];
          final weight = p['weight_kg'];
          final maxHr = p['max_hr'];
          if (profileName.trim().isEmpty ||
              profileName.length > 200 ||
              ftp != null && (ftp is! int || ftp < 30 || ftp > 2000) ||
              weight != null &&
                  (weight is! num ||
                      !weight.isFinite ||
                      weight < 10 ||
                      weight > 500) ||
              maxHr != null && (maxHr is! int || maxHr < 50 || maxHr > 250)) {
            throw const FormatException('Invalid profile.');
          }
        case 'workout':
          requiredField<String>('name');
          requiredField<List>('blocks');
          if (p['description'] != null) requiredField<String>('description');
          if (p['category'] != null) requiredField<String>('category');
          for (final b in WorkoutRecord(r).blocks) {
            if (!['steady', 'ramp'].contains(b.type) || b.duration <= 0) {
              throw const FormatException('Invalid workout block.');
            }
          }
        case 'plan':
          if (r.revision < 1) {
            throw const FormatException('Invalid synchronized plan revision.');
          }
          PlanRecord(r);
        case 'session':
          requiredField<String>('status');
          requiredField<String>('workout_name');
          requiredField<int>('duration_sec');
          requiredField<String>('timestamp');
          _validateSessionPayload(p);
      }
    }
  }
  final List<SyncRecord> records;
  Iterable<SyncRecord> active(String kind) =>
      records.where((r) => r.kind == kind && !r.deleted);
  List<ProfileRecord> get profiles =>
      active('profile').map(ProfileRecord.new).toList();
  List<WorkoutRecord> get workouts =>
      active('workout').map(WorkoutRecord.new).toList()
        ..sort((a, b) => a.name.compareTo(b.name));
  List<SessionRecord> get sessions =>
      active('session').map(SessionRecord.new).toList();
  List<PlanRecord> upcoming(DateTime now) {
    final day =
        '${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    final completed = sessions
        .where((s) => s.status == 'completed')
        .map((s) => s.planId)
        .whereType<String>()
        .toList();
    return active('plan')
        .map(PlanRecord.new)
        .where(
          (p) =>
              p.date.compareTo(day) >= 0 &&
              !completed.any((planId) => sameUuid(planId, p.record.id)),
        )
        .toList()
      ..sort((a, b) => a.date.compareTo(b.date));
  }
}
