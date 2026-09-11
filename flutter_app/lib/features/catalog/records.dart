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
  PlanRecord(this.record);
  final SyncRecord record;
  String get date => record.payload['date'] as String;
  String get workoutId => record.payload['workout_id'] as String;
  String get workoutName => record.payload['workout_name'] as String;
}

class SessionRecord {
  SessionRecord(this.record);
  final SyncRecord record;
  String? get planId => record.payload['plan_id'] as String?;
  String get status => record.payload['status'] as String;
  String get workoutName => record.payload['workout_name'] as String;
  DateTime get timestamp =>
      DateTime.parse(record.payload['timestamp'] as String);
  int get duration => record.payload['duration_sec'] as int;
  Map<String, dynamic>? get metrics =>
      record.payload['metrics'] as Map<String, dynamic>?;
  List<dynamic>? get samples => record.payload['samples'] as List?;
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
          if (p['ftp'] != null) requiredField<int>('ftp');
          if (p['weight_kg'] != null) requiredField<num>('weight_kg');
          if (p['max_hr'] != null) requiredField<int>('max_hr');
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
          requiredField<String>('date');
          requiredField<String>('workout_id');
          requiredField<String>('workout_name');
          final date = p['date'] as String;
          final parsed = DateTime.tryParse(date);
          if (parsed == null ||
              parsed.toIso8601String().substring(0, 10) != date) {
            throw const FormatException('Invalid plan date.');
          }
        case 'session':
          requiredField<String>('status');
          requiredField<String>('workout_name');
          requiredField<int>('duration_sec');
          requiredField<String>('timestamp');
          if (p['plan_id'] != null) requiredField<String>('plan_id');
          if (p['metrics'] != null) {
            requiredField<Map<String, dynamic>>('metrics');
          }
          if (p['samples'] != null) requiredField<List>('samples');
          if (DateTime.tryParse(p['timestamp'] as String) == null) {
            throw const FormatException('Invalid session timestamp.');
          }
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
        .toSet();
    return active('plan')
        .map(PlanRecord.new)
        .where(
          (p) => p.date.compareTo(day) >= 0 && !completed.contains(p.record.id),
        )
        .toList()
      ..sort((a, b) => a.date.compareTo(b.date));
  }
}
