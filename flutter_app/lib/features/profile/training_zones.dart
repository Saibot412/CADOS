import 'dart:math' as math;

class TrainingZone {
  const TrainingZone({
    required this.code,
    required this.name,
    required this.lower,
    required this.upper,
    required this.rangeLabel,
    required this.percentLabel,
    required this.colorHex,
  });

  final String code;
  final String name;
  final int lower;
  final int? upper;
  final String rangeLabel;
  final String percentLabel;
  final String colorHex;

  String get label => '$code $name';

  @override
  bool operator ==(Object other) =>
      other is TrainingZone &&
      code == other.code &&
      name == other.name &&
      lower == other.lower &&
      upper == other.upper &&
      rangeLabel == other.rangeLabel &&
      percentLabel == other.percentLabel &&
      colorHex == other.colorHex;

  @override
  int get hashCode =>
      Object.hash(code, name, lower, upper, rangeLabel, percentLabel, colorHex);
}

class _ZoneDefinition {
  const _ZoneDefinition(
    this.code,
    this.name,
    this.lowerRatio,
    this.upperRatio,
    this.colorHex,
  );
  final String code, name, colorHex;
  final double lowerRatio;
  final double? upperRatio;
}

const _powerDefinitions = [
  _ZoneDefinition('Z1', 'Recovery', 0, .55, '#8B98A7'),
  _ZoneDefinition('Z2', 'Endurance', .56, .75, '#2E86FF'),
  _ZoneDefinition('Z3', 'Tempo', .76, .90, '#2FBF71'),
  _ZoneDefinition('Z4', 'Threshold', .91, 1.05, '#F2C94C'),
  _ZoneDefinition('Z5', 'VO2 Max', 1.06, 1.20, '#FF9F43'),
  _ZoneDefinition('Z6', 'Anaerobic', 1.21, 1.50, '#EB5757'),
  _ZoneDefinition('Z7', 'Neuromuscular', 1.51, null, '#9B51E0'),
];

const _heartRateDefinitions = [
  _ZoneDefinition('H1', 'Erholung', 0, .60, '#8B98A7'),
  _ZoneDefinition('H2', 'Grundlage', .61, .70, '#2E86FF'),
  _ZoneDefinition('H3', 'Aerob', .71, .80, '#2FBF71'),
  _ZoneDefinition('H4', 'Schwelle', .81, .90, '#FF9F43'),
  _ZoneDefinition('H5', 'Maximum', .91, null, '#EB5757'),
];

int roundHalfUp(num value) => (value + .5).floor();

List<TrainingZone> powerZones(int ftpWatts) {
  if (ftpWatts <= 0) throw ArgumentError.value(ftpWatts, 'ftpWatts');
  return _buildZones(_powerDefinitions, ftpWatts, 'W', 'FTP');
}

TrainingZone powerZoneForWatts(num watts, int ftpWatts) =>
    _zoneFor(math.max(0, watts), powerZones(ftpWatts));

List<TrainingZone> heartRateZones(int maxHeartRate) {
  if (maxHeartRate <= 0) {
    throw ArgumentError.value(maxHeartRate, 'maxHeartRate');
  }
  return _buildZones(_heartRateDefinitions, maxHeartRate, 'bpm', 'HFmax');
}

TrainingZone heartRateZoneForBpm(num bpm, int maxHeartRate) =>
    _zoneFor(math.max(0, bpm), heartRateZones(maxHeartRate));

List<TrainingZone> _buildZones(
  List<_ZoneDefinition> definitions,
  int anchor,
  String unit,
  String percentAnchor,
) {
  var previousUpper = 0;
  return List.unmodifiable([
    for (var index = 0; index < definitions.length; index++)
      () {
        final definition = definitions[index];
        final upper = definition.upperRatio == null
            ? null
            : roundHalfUp(anchor * definition.upperRatio!);
        final lower = index == 0 ? 0 : previousUpper + 1;
        if (upper != null) previousUpper = upper;
        final lowerPercent = index == 0
            ? 0
            : roundHalfUp(definition.lowerRatio * 100);
        final upperPercent = definition.upperRatio == null
            ? null
            : roundHalfUp(definition.upperRatio! * 100);
        return TrainingZone(
          code: definition.code,
          name: definition.name,
          lower: lower,
          upper: upper,
          rangeLabel: upper == null ? '$lower+ $unit' : '$lower-$upper $unit',
          percentLabel: upperPercent == null
              ? '$lowerPercent%+ $percentAnchor'
              : '$lowerPercent-$upperPercent% $percentAnchor',
          colorHex: definition.colorHex,
        );
      }(),
  ]);
}

TrainingZone _zoneFor(num value, List<TrainingZone> zones) => zones.firstWhere(
  (zone) => zone.upper == null || value <= zone.upper!,
  orElse: () => zones.last,
);
