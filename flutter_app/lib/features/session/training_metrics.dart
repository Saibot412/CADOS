import 'dart:collection';
import 'dart:math' as math;

import '../workout/workout.dart';

/// Time-weighted rider measurements with one-second power bins.
///
/// Binning makes rolling power, normalized power and the best minute independent
/// of the caller's telemetry/tick frequency. A pause starts a new power window.
class TrainingMetrics {
  double activeSeconds = 0;
  double energyJoules = 0;
  double _cadenceSum = 0;
  double _cadenceSeconds = 0;
  double _heartRateSum = 0;
  double _heartRateSeconds = 0;
  double _binTime = 0;
  double _binEnergy = 0;
  double _normalizedPowerFourthSum = 0;
  int _normalizedPowerCount = 0;
  final Queue<double> _seconds = Queue<double>();

  int maxWatts = 0;
  double maxCadence = 0;
  int maxHeartRate = 0;
  double bestMinute = 0;

  void breakPowerWindow() {
    _seconds.clear();
    _binTime = 0;
    _binEnergy = 0;
  }

  void add(double dt, int watts, num? cadence, int? heartRate) {
    if (!dt.isFinite || dt <= 0) return;
    watts = math.max(0, watts);
    activeSeconds += dt;
    energyJoules += watts * dt;
    maxWatts = math.max(maxWatts, watts);
    if (cadence != null && cadence.isFinite && cadence >= 0) {
      _cadenceSum += cadence * dt;
      _cadenceSeconds += dt;
      maxCadence = math.max(maxCadence, cadence.toDouble());
    }
    if (heartRate != null && heartRate > 0) {
      _heartRateSum += heartRate * dt;
      _heartRateSeconds += dt;
      if (heartRate >= 50 && heartRate <= 250) {
        maxHeartRate = math.max(maxHeartRate, heartRate);
      }
    }

    var remaining = dt;
    while (remaining > 1e-9) {
      final portion = math.min(remaining, 1 - _binTime);
      _binTime += portion;
      _binEnergy += watts * portion;
      remaining -= portion;
      if (_binTime >= 1 - 1e-9) {
        _seconds.add(_binEnergy / _binTime);
        if (_seconds.length > 60) _seconds.removeFirst();
        _binTime = 0;
        _binEnergy = 0;
        if (_seconds.length >= 30) {
          final values = _seconds.toList(growable: false);
          final rolling =
              values
                  .sublist(values.length - 30)
                  .fold<double>(0, (sum, value) => sum + value) /
              30;
          _normalizedPowerFourthSum += math.pow(rolling, 4).toDouble();
          _normalizedPowerCount++;
        }
        if (_seconds.length == 60) {
          final minute =
              _seconds.fold<double>(0, (sum, value) => sum + value) / 60;
          bestMinute = math.max(bestMinute, minute);
        }
      }
    }
  }

  Map<String, num> summary(int ftp) {
    final average = activeSeconds > 0
        ? pythonRound(energyJoules / activeSeconds)
        : 0;
    final normalizedPower = _normalizedPowerCount > 0
        ? pythonRound(
            math
                .pow(_normalizedPowerFourthSum / _normalizedPowerCount, .25)
                .toDouble(),
          )
        : average;
    final intensity = ftp > 0 ? normalizedPower / ftp : 0.0;
    return {
      'max_watts': maxWatts,
      'avg_watts': average,
      'max_cadence': pythonRound(maxCadence),
      'avg_cadence': _cadenceSeconds > 0
          ? pythonRound(_cadenceSum / _cadenceSeconds)
          : 0,
      'max_heart_rate': maxHeartRate,
      'avg_heart_rate': _heartRateSeconds > 0
          ? pythonRound(_heartRateSum / _heartRateSeconds)
          : 0,
      'best_minute_watts': pythonRound(bestMinute),
      'work_kj': _roundTo(energyJoules / 1000, 1),
      'normalized_power': normalizedPower,
      'intensity_factor': _roundTo(intensity, 2),
      'tss': _roundTo(activeSeconds / 3600 * intensity * intensity * 100, 1),
      // Retained for Python/server/UI compatibility: mechanical kJ rounded to
      // an integer is the existing CADOS calories estimate.
      'calories': pythonRound(energyJoules / 1000),
    };
  }
}

double _roundTo(double value, int places) {
  final factor = math.pow(10, places).toDouble();
  return pythonRound(value * factor) / factor;
}
