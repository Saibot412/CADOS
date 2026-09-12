import '../../core/json_value.dart';
import '../catalog/records.dart';

const _ownedPlanFields = {'date', 'workout_id', 'workout_name'};

/// Immutable editable plan payload that retains server-owned extensions.
class PlanDraft {
  PlanDraft({
    required this.date,
    required this.workoutId,
    required this.workoutName,
    Map<String, dynamic> extraFields = const {},
  }) : _extraFields = _freezeExtras(extraFields);

  factory PlanDraft.fromRecord(PlanRecord plan) => PlanDraft(
    date: plan.date,
    workoutId: plan.workoutId,
    workoutName: plan.workoutName,
    extraFields: plan.record.payload,
  );

  factory PlanDraft.fromJson(Map<String, dynamic> payload) {
    PlanRecord.validatePayload(payload);
    return PlanDraft(
      date: payload['date'] as String,
      workoutId: payload['workout_id'] as String,
      workoutName: payload['workout_name'] as String,
      extraFields: payload,
    );
  }

  final String date;
  final String workoutId;
  final String workoutName;
  final Map<String, dynamic> _extraFields;

  Map<String, dynamic> get extraFields => _extraFields;

  PlanDraft copyWith({
    String? date,
    String? workoutId,
    String? workoutName,
    Map<String, dynamic>? extraFields,
  }) => PlanDraft(
    date: date ?? this.date,
    workoutId: workoutId ?? this.workoutId,
    workoutName: workoutName ?? this.workoutName,
    extraFields: extraFields ?? _extraFields,
  );

  /// Uses the supplied date's own calendar components; no UTC conversion occurs.
  PlanDraft updateDate(DateTime localDate) => copyWith(
    date:
        '${localDate.year.toString().padLeft(4, '0')}-'
        '${localDate.month.toString().padLeft(2, '0')}-'
        '${localDate.day.toString().padLeft(2, '0')}',
  );

  PlanDraft updateWorkout(WorkoutRecord workout) =>
      copyWith(workoutId: workout.record.id, workoutName: workout.name.trim());

  WorkoutRecord? visibleWorkout(Catalog authoritativeCatalog) {
    for (final workout in authoritativeCatalog.workouts) {
      if (sameUuid(workout.record.id, workoutId)) return workout;
    }
    return null;
  }

  bool isWorkoutStartable(Catalog authoritativeCatalog) =>
      visibleWorkout(authoritativeCatalog) != null;

  /// Builds a fresh payload only when all resulting owned values are valid.
  Map<String, dynamic> toJson() {
    final payload = <String, dynamic>{
      ..._thawMap(_extraFields),
      'date': date,
      'workout_id': workoutId,
      'workout_name': workoutName.trim(),
    };
    PlanRecord.validatePayload(payload);
    return payload;
  }
}

Map<String, dynamic> _freezeExtras(Map<String, dynamic> fields) {
  final extras = <String, dynamic>{
    for (final entry in fields.entries)
      if (!_ownedPlanFields.contains(entry.key)) entry.key: entry.value,
  };
  return freezeJson(extras) as Map<String, dynamic>;
}

Map<String, dynamic> _thawMap(Map<String, dynamic> value) =>
    value.map((key, item) => MapEntry(key, _thawJson(item)));

dynamic _thawJson(dynamic value) {
  if (value is Map<String, dynamic>) return _thawMap(value);
  if (value is List) return value.map(_thawJson).toList();
  return value;
}
