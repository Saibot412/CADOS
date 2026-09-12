import 'dart:math' as math;

import '../workout/workout.dart';
import 'training_metrics.dart';

bool isFtpRamp(String name) {
  final folded = name.toLowerCase();
  return folded.contains('ftp') && folded.contains('ramp');
}

/// Local counterpart of the server assessment. Only measured power from the
/// Step/Stufe section is eligible; targets and warm-up samples are never used.
Map<String, dynamic>? ftpTestResult(Map<String, dynamic> payload) {
  if (!isFtpRamp(payload['workout_name']?.toString() ?? '')) return null;
  final workoutPayload = payload['workout_payload'];
  final blocks = workoutPayload is Map ? workoutPayload['blocks'] : null;
  double? start;
  double? end;
  var cursor = 0.0;
  if (blocks is List) {
    for (final raw in blocks) {
      if (raw is! Map) continue;
      final durationValue = raw['duration_sec'];
      if (durationValue is! num ||
          !durationValue.isFinite ||
          durationValue < 0) {
        return null;
      }
      final duration = durationValue.toDouble();
      final label = raw['label']?.toString().toLowerCase() ?? '';
      if (label.startsWith('step ') || label.startsWith('stufe ')) {
        start ??= cursor;
        end = cursor + duration;
      }
      cursor += duration;
    }
  }
  final result = <String, dynamic>{
    'old_ftp': payload['ftp_watts'],
    'method': '75_percent_best_continuous_minute',
    'eligible': false,
  };
  if (start == null || end == null) {
    return {
      ...result,
      'reason': 'Für diesen Test ist kein auswertbarer Stufenteil hinterlegt.',
    };
  }

  final metrics = TrainingMetrics();
  double? previousEnd;
  Object? segment;
  var counted = 0.0;
  final samples = payload['samples'];
  if (samples is List) {
    for (final raw in samples) {
      if (raw is! Map) continue;
      final dtValue = raw['duration_sec'];
      final elapsedValue = raw['workout_elapsed_sec'];
      final wattsValue = raw['watts'];
      if (dtValue is! num ||
          elapsedValue is! num ||
          wattsValue is! num ||
          !dtValue.isFinite ||
          !elapsedValue.isFinite ||
          !wattsValue.isFinite) {
        continue;
      }
      final dt = dtValue.toDouble();
      final elapsed = elapsedValue.toDouble();
      final watts = wattsValue.toDouble();
      if (dt <= 0 || dt > 86400 || watts < 0 || watts > 32767) continue;
      final lower = math.max(start, elapsed);
      final upper = math.min(end, elapsed + dt);
      if (upper <= lower) continue;
      final currentSegment = raw['segment'] ?? 0;
      if (segment != currentSegment ||
          (previousEnd != null && (lower - previousEnd).abs() > .01)) {
        metrics.breakPowerWindow();
      }
      segment = currentSegment;
      previousEnd = upper;
      final length = math.min(upper - lower, 86400 - counted);
      if (length <= 0) break;
      counted += length;
      metrics.add(length, watts.toInt(), null, null);
    }
  }
  final best = pythonRound(metrics.bestMinute);
  final estimate = pythonRound(metrics.bestMinute * .75);
  if (estimate < 30 || estimate > 2000) {
    return {
      ...result,
      'reason': 'Im Belastungsteil fehlt eine vollständige, zusammenhängende Minute mit verwertbarer Leistung.',
    };
  }
  return {
    ...result,
    'eligible': true,
    'best_minute_watts': best,
    'estimated_ftp': estimate,
  };
}
