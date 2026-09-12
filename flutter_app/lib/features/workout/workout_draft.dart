import 'workout_validator.dart';

const _unchanged = Object();

/// Editable, immutable representation of a workout payload.
class WorkoutDraft {
  WorkoutDraft({
    required this.name,
    required List<WorkoutBlockDraft> blocks,
    Map<String, dynamic> metadata = const {},
  }) : blocks = List.unmodifiable(blocks),
       _metadata = _freezeMap(_withoutKeys(metadata, const {'name', 'blocks'}));

  factory WorkoutDraft.fromJson(Map<String, dynamic> payload) {
    WorkoutValidator.validatePayload(payload);
    return WorkoutDraft(
      name: payload['name'] as String,
      blocks: [
        for (final block in payload['blocks'] as List<dynamic>)
          WorkoutBlockDraft.fromJson(block as Map<String, dynamic>),
      ],
      metadata: _withoutKeys(payload, const {'name', 'blocks'}),
    );
  }

  final String name;
  final List<WorkoutBlockDraft> blocks;
  final Map<String, dynamic> _metadata;

  Map<String, dynamic> get metadata => _metadata;

  WorkoutDraft copyWith({
    String? name,
    List<WorkoutBlockDraft>? blocks,
    Map<String, dynamic>? metadata,
  }) => WorkoutDraft(
    name: name ?? this.name,
    blocks: blocks ?? this.blocks,
    metadata: metadata ?? _metadata,
  );

  WorkoutDraft addBlock(WorkoutBlockDraft block, {int? index}) {
    final insertionIndex = index ?? blocks.length;
    RangeError.checkValueInInterval(insertionIndex, 0, blocks.length, 'index');
    final updated = blocks.toList()..insert(insertionIndex, block);
    return copyWith(blocks: updated);
  }

  WorkoutDraft removeBlock(int index) {
    RangeError.checkValidIndex(index, blocks, 'index');
    final updated = blocks.toList()..removeAt(index);
    return copyWith(blocks: updated);
  }

  WorkoutDraft updateBlock(int index, WorkoutBlockDraft block) {
    RangeError.checkValidIndex(index, blocks, 'index');
    final updated = blocks.toList()..[index] = block;
    return copyWith(blocks: updated);
  }

  /// Moves the block at [from] to final index [to].
  WorkoutDraft reorderBlock(int from, int to) {
    RangeError.checkValidIndex(from, blocks, 'from');
    RangeError.checkValidIndex(to, blocks, 'to');
    if (from == to) return this;
    final updated = blocks.toList();
    final block = updated.removeAt(from);
    updated.insert(to, block);
    return copyWith(blocks: updated);
  }

  WorkoutDraft moveBlock(int from, int to) => reorderBlock(from, to);

  /// Serializes only after the complete resulting payload passes validation.
  Map<String, dynamic> toJson() {
    final payload = <String, dynamic>{
      ..._thawMap(_metadata),
      'name': name,
      'blocks': [for (final block in blocks) block._toJsonUnchecked()],
    };
    WorkoutValidator.validatePayload(payload);
    return payload;
  }
}

sealed class WorkoutBlockDraft {
  WorkoutBlockDraft({
    required this.durationSec,
    this.label,
    this.targetCadence,
    Map<String, dynamic> extraFields = const {},
  }) : _extraFields = _freezeMap(extraFields);

  factory WorkoutBlockDraft.fromJson(Map<String, dynamic> json) {
    switch (json['type']) {
      case 'steady':
        return SteadyBlockDraft._fromJson(json);
      case 'ramp':
        return RampBlockDraft._fromJson(json);
      default:
        throw const FormatException('Unbekannter Blocktyp.');
    }
  }

  final int durationSec;
  final String? label;
  final int? targetCadence;
  final Map<String, dynamic> _extraFields;

  Map<String, dynamic> get extraFields => _extraFields;

  String get type;

  Map<String, dynamic> _toJsonUnchecked();

  Map<String, dynamic> _commonJson() => <String, dynamic>{
    ..._thawMap(_extraFields),
    'type': type,
    'duration_sec': durationSec,
    if (label != null) 'label': label,
    if (targetCadence != null) 'target_cadence': targetCadence,
  };
}

class SteadyBlockDraft extends WorkoutBlockDraft {
  SteadyBlockDraft({
    required super.durationSec,
    super.label,
    super.targetCadence,
    this.targetPctFtp,
    this.targetWatts,
    Map<String, dynamic> extraFields = const {},
  }) : super(
         extraFields: _withoutKeys(extraFields, const {
           'type',
           'duration_sec',
           'label',
           'target_cadence',
           'target_pct_ftp',
           'target_watts',
         }),
       );

  SteadyBlockDraft._fromJson(Map<String, dynamic> json)
    : targetPctFtp = (json['target_pct_ftp'] as num?)?.toDouble(),
      targetWatts = (json['target_watts'] as num?)?.toInt(),
      super(
        durationSec: json['duration_sec'] as int,
        label: json['label'] as String?,
        targetCadence: json['target_cadence'] as int?,
        extraFields: _extrasPreservingNulls(json, const {
          'type',
          'duration_sec',
          'label',
          'target_cadence',
          'target_pct_ftp',
          'target_watts',
        }),
      );

  @override
  String get type => 'steady';
  final double? targetPctFtp;
  final int? targetWatts;

  bool get usesFtpTarget => targetPctFtp != null;

  SteadyBlockDraft copyWith({
    int? durationSec,
    Object? label = _unchanged,
    Object? targetCadence = _unchanged,
    Object? targetPctFtp = _unchanged,
    Object? targetWatts = _unchanged,
    Map<String, dynamic>? extraFields,
  }) => SteadyBlockDraft(
    durationSec: durationSec ?? this.durationSec,
    label: identical(label, _unchanged) ? this.label : label as String?,
    targetCadence: identical(targetCadence, _unchanged)
        ? this.targetCadence
        : targetCadence as int?,
    targetPctFtp: identical(targetPctFtp, _unchanged)
        ? this.targetPctFtp
        : targetPctFtp as double?,
    targetWatts: identical(targetWatts, _unchanged)
        ? this.targetWatts
        : targetWatts as int?,
    extraFields: extraFields ?? _extraFields,
  );

  @override
  Map<String, dynamic> _toJsonUnchecked() => <String, dynamic>{
    ..._commonJson(),
    if (targetPctFtp != null) 'target_pct_ftp': targetPctFtp,
    if (targetWatts != null) 'target_watts': targetWatts,
  };
}

class RampBlockDraft extends WorkoutBlockDraft {
  RampBlockDraft({
    required super.durationSec,
    super.label,
    super.targetCadence,
    this.startPctFtp,
    this.startWatts,
    this.endPctFtp,
    this.endWatts,
    Map<String, dynamic> extraFields = const {},
  }) : super(
         extraFields: _withoutKeys(extraFields, const {
           'type',
           'duration_sec',
           'label',
           'target_cadence',
           'start_pct_ftp',
           'start_watts',
           'end_pct_ftp',
           'end_watts',
         }),
       );

  RampBlockDraft._fromJson(Map<String, dynamic> json)
    : startPctFtp = (json['start_pct_ftp'] as num?)?.toDouble(),
      startWatts = (json['start_watts'] as num?)?.toInt(),
      endPctFtp = (json['end_pct_ftp'] as num?)?.toDouble(),
      endWatts = (json['end_watts'] as num?)?.toInt(),
      super(
        durationSec: json['duration_sec'] as int,
        label: json['label'] as String?,
        targetCadence: json['target_cadence'] as int?,
        extraFields: _extrasPreservingNulls(json, const {
          'type',
          'duration_sec',
          'label',
          'target_cadence',
          'start_pct_ftp',
          'start_watts',
          'end_pct_ftp',
          'end_watts',
        }),
      );

  @override
  String get type => 'ramp';
  final double? startPctFtp;
  final int? startWatts;
  final double? endPctFtp;
  final int? endWatts;

  bool get usesFtpStart => startPctFtp != null;
  bool get usesFtpEnd => endPctFtp != null;

  RampBlockDraft copyWith({
    int? durationSec,
    Object? label = _unchanged,
    Object? targetCadence = _unchanged,
    Object? startPctFtp = _unchanged,
    Object? startWatts = _unchanged,
    Object? endPctFtp = _unchanged,
    Object? endWatts = _unchanged,
    Map<String, dynamic>? extraFields,
  }) => RampBlockDraft(
    durationSec: durationSec ?? this.durationSec,
    label: identical(label, _unchanged) ? this.label : label as String?,
    targetCadence: identical(targetCadence, _unchanged)
        ? this.targetCadence
        : targetCadence as int?,
    startPctFtp: identical(startPctFtp, _unchanged)
        ? this.startPctFtp
        : startPctFtp as double?,
    startWatts: identical(startWatts, _unchanged)
        ? this.startWatts
        : startWatts as int?,
    endPctFtp: identical(endPctFtp, _unchanged)
        ? this.endPctFtp
        : endPctFtp as double?,
    endWatts: identical(endWatts, _unchanged)
        ? this.endWatts
        : endWatts as int?,
    extraFields: extraFields ?? _extraFields,
  );

  @override
  Map<String, dynamic> _toJsonUnchecked() => <String, dynamic>{
    ..._commonJson(),
    if (startPctFtp != null) 'start_pct_ftp': startPctFtp,
    if (startWatts != null) 'start_watts': startWatts,
    if (endPctFtp != null) 'end_pct_ftp': endPctFtp,
    if (endWatts != null) 'end_watts': endWatts,
  };
}

Map<String, dynamic> _withoutKeys(
  Map<String, dynamic> source,
  Set<String> keys,
) => <String, dynamic>{
  for (final entry in source.entries)
    if (!keys.contains(entry.key)) entry.key: entry.value,
};

Map<String, dynamic> _extrasPreservingNulls(
  Map<String, dynamic> source,
  Set<String> knownKeys,
) => <String, dynamic>{
  for (final entry in source.entries)
    if (!knownKeys.contains(entry.key) ||
        entry.value == null &&
            entry.key != 'type' &&
            entry.key != 'duration_sec')
      entry.key: entry.value,
};

Map<String, dynamic> _freezeMap(Map<String, dynamic> source) =>
    Map.unmodifiable({
      for (final entry in source.entries) entry.key: _freeze(entry.value),
    });

Object? _freeze(Object? value) {
  if (value is Map) {
    return Map.unmodifiable({
      for (final entry in value.entries) entry.key: _freeze(entry.value),
    });
  }
  if (value is List) return List.unmodifiable(value.map(_freeze));
  return value;
}

Map<String, dynamic> _thawMap(Map<String, dynamic> source) => {
  for (final entry in source.entries) entry.key: _thaw(entry.value),
};

Object? _thaw(Object? value) {
  if (value is Map) {
    if (value.keys.every((key) => key is String)) {
      return <String, dynamic>{
        for (final entry in value.entries)
          entry.key as String: _thaw(entry.value),
      };
    }
    return <dynamic, dynamic>{
      for (final entry in value.entries) entry.key: _thaw(entry.value),
    };
  }
  if (value is List) return [for (final item in value) _thaw(item)];
  return value;
}
