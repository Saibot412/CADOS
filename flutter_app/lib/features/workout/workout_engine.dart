import 'dart:math' as math;

import 'workout.dart';

enum WorkoutState {
  ready,
  waitingForPedal,
  running,
  paused,
  stopped,
  completed,
}

/// Deterministic control math only. Caller supplies elapsed time and telemetry;
/// this engine never sends trainer commands or starts a timer.
class WorkoutEngine {
  WorkoutEngine(this.workout);
  static const _adaptiveErgDeadbandRpm = 3;
  static const _adaptiveErgTriggerSeconds = 2.0;
  static const _adaptiveErgMaximumReliefRatio = 0.10;
  static const _adaptiveErgReliefWattsPerSecond = 5.0;
  static const _adaptiveErgRecoveryWattsPerSecond = 4.0;

  final Workout workout;
  WorkoutState state = WorkoutState.ready;
  double elapsed = 0, _zero = 0, _ramp = 0, _transition = 0;
  double _adaptiveLowCadenceSeconds = 0, _adaptiveReliefWatts = 0;
  int adjustment = 0, _lastIndex = -1, _lastTarget = 0;
  int? _transitionFrom;
  bool _adaptiveErgEnabled = false;
  bool ramping = false, autoPaused = false, _ftpCadenceSeen = false;
  bool get isFtpTest {
    final name = workout.name.toLowerCase();
    return name.contains('ftp') && name.contains('ramp');
  }

  int get blockIndex => workout.locate(elapsed).$1;
  int? get targetCadence => workout.locate(elapsed).$2.cadence;
  bool get adaptiveErgEnabled => _adaptiveErgEnabled;
  int get adaptiveReliefWatts => pythonRound(_adaptiveReliefWatts);
  int get trainerTargetWatts =>
      (targetWatts - (_adaptiveErgEnabled ? adaptiveReliefWatts : 0)).clamp(
        0,
        32767,
      );
  int get targetWatts {
    final (_, block, seconds) = workout.locate(elapsed);
    var target = (block.targetAt(seconds) + adjustment).clamp(0, 32767);
    if (_transitionFrom != null && !ramping) {
      target = pythonRound(
        _transitionFrom! +
            (target - _transitionFrom!) * (_transition / 3).clamp(0, 1),
      );
    }
    if (ramping) {
      target = pythonRound(30 + (target - 30) * (_ramp / 5).clamp(0, 1));
    }
    return target;
  }

  void setAdaptiveErg(bool enabled) {
    _adaptiveErgEnabled = enabled && !isFtpTest;
    _resetAdaptiveErg();
  }

  void start() {
    if (![
      WorkoutState.ready,
      WorkoutState.stopped,
      WorkoutState.completed,
    ].contains(state)) {
      return;
    }
    elapsed = 0;
    adjustment = 0;
    _zero = 0;
    _ramp = 0;
    _lastIndex = -1;
    _lastTarget = 0;
    _transitionFrom = null;
    ramping = false;
    autoPaused = false;
    _ftpCadenceSeen = false;
    _resetAdaptiveErg();
    state = WorkoutState.waitingForPedal;
  }

  void pause() {
    if (state == WorkoutState.running ||
        state == WorkoutState.waitingForPedal) {
      state = WorkoutState.paused;
      autoPaused = false;
      ramping = false;
      _resetAdaptiveErg();
    }
  }

  void resume() {
    if (state == WorkoutState.paused) {
      state = WorkoutState.waitingForPedal;
      autoPaused = false;
      _zero = 0;
      _resetAdaptiveErg();
    }
  }

  void stop() {
    state = WorkoutState.stopped;
    ramping = false;
    autoPaused = false;
    _transitionFrom = null;
    _resetAdaptiveErg();
  }

  void adjustTarget(int delta) {
    if ([
      WorkoutState.running,
      WorkoutState.paused,
      WorkoutState.waitingForPedal,
    ].contains(state)) {
      adjustment += delta;
    }
  }

  void tick(
    double dt, {
    required bool connected,
    required int currentWatts,
    double? currentCadence,
  }) {
    if (!dt.isFinite) throw ArgumentError('Non-finite tick');
    dt = math.max(0, dt);
    if (state == WorkoutState.running && (!connected || dt > 5)) {
      state = WorkoutState.paused;
      autoPaused = dt <= 5;
      ramping = false;
      _transitionFrom = null;
      _resetAdaptiveErg();
      return;
    }
    if (state == WorkoutState.waitingForPedal ||
        (state == WorkoutState.paused && autoPaused)) {
      if (connected && currentWatts > 0) {
        state = WorkoutState.running;
        autoPaused = false;
        ramping = true;
        _ramp = 0;
        _zero = 0;
        _update(0);
      }
      return;
    }
    if (state != WorkoutState.running) return;
    final label = workout.locate(elapsed).$2.label.toLowerCase();
    final inTestStage =
        isFtpTest && (label.startsWith('step ') || label.startsWith('stufe '));
    if (inTestStage && currentCadence != null) {
      if (currentCadence > 0) {
        _ftpCadenceSeen = true;
      } else if (currentCadence == 0 && _ftpCadenceSeen) {
        state = WorkoutState.completed;
        ramping = false;
        return;
      }
    }
    dt = math.min(dt, workout.duration - elapsed);
    if (currentWatts <= 0) {
      dt = math.min(dt, math.max(0, 2 - _zero));
      _zero += dt;
    } else {
      _zero = 0;
    }
    elapsed += dt;
    _update(dt);
    _updateAdaptiveErg(currentCadence, dt);
    if (elapsed >= workout.duration) {
      state = WorkoutState.completed;
      _resetAdaptiveErg();
    } else if (_zero >= 2) {
      state = WorkoutState.paused;
      autoPaused = true;
      ramping = false;
      _transitionFrom = null;
      _resetAdaptiveErg();
    }
  }

  /// Recovery keeps cadence-finish state without issuing commands or advancing.
  void restoreFtpCadenceSeen(Iterable<Map<String, dynamic>> samples) {
    if (!isFtpTest) return;
    for (final sample in samples) {
      final elapsedValue = sample['workout_elapsed_sec'];
      final cadence = sample['cadence'];
      if (elapsedValue is! num || cadence is! num || cadence <= 0) continue;
      final label = workout
          .locate(elapsedValue.toDouble())
          .$2
          .label
          .toLowerCase();
      if (label.startsWith('step ') || label.startsWith('stufe ')) {
        _ftpCadenceSeen = true;
        return;
      }
    }
  }

  void _update(double dt) {
    if (ramping) {
      _ramp += dt;
      if (_ramp >= 5) ramping = false;
    }
    if (_transitionFrom != null) {
      _transition += dt;
      if (_transition >= 3) _transitionFrom = null;
    }
    if (state == WorkoutState.running &&
        _lastIndex >= 0 &&
        blockIndex != _lastIndex) {
      _transitionFrom = _lastTarget;
      _transition = 0;
      _resetAdaptiveErg();
    }
    _lastIndex = blockIndex;
    _lastTarget = targetWatts;
  }

  void _updateAdaptiveErg(double? cadence, double dt) {
    if (!_adaptiveErgEnabled || state != WorkoutState.running) {
      _resetAdaptiveErg();
      return;
    }
    final cadenceTarget = targetCadence;
    final wattsTarget = targetWatts;
    if (cadenceTarget == null ||
        cadenceTarget == 0 ||
        cadence == null ||
        cadence <= 0 ||
        wattsTarget <= 0) {
      _adaptiveLowCadenceSeconds = 0;
      _adaptiveReliefWatts = math.max(
        0,
        _adaptiveReliefWatts - _adaptiveErgRecoveryWattsPerSecond * dt,
      );
      return;
    }

    final deficit = cadenceTarget - cadence - _adaptiveErgDeadbandRpm;
    if (deficit > 0) {
      _adaptiveLowCadenceSeconds += dt;
      final maximum = wattsTarget * _adaptiveErgMaximumReliefRatio;
      final desired = maximum * math.min(1, deficit / 12);
      if (_adaptiveLowCadenceSeconds >= _adaptiveErgTriggerSeconds) {
        _adaptiveReliefWatts = math.min(
          desired,
          _adaptiveReliefWatts + _adaptiveErgReliefWattsPerSecond * dt,
        );
      }
      return;
    }

    _adaptiveLowCadenceSeconds = 0;
    _adaptiveReliefWatts = math.max(
      0,
      _adaptiveReliefWatts - _adaptiveErgRecoveryWattsPerSecond * dt,
    );
  }

  void _resetAdaptiveErg() {
    _adaptiveLowCadenceSeconds = 0;
    _adaptiveReliefWatts = 0;
  }
}
