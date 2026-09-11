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
  final Workout workout;
  WorkoutState state = WorkoutState.ready;
  double elapsed = 0, _zero = 0, _ramp = 0, _transition = 0;
  int adjustment = 0, _lastIndex = -1, _lastTarget = 0;
  int? _transitionFrom;
  bool ramping = false, autoPaused = false;
  int get blockIndex => workout.locate(elapsed).$1;
  int? get targetCadence => workout.locate(elapsed).$2.cadence;
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
    state = WorkoutState.waitingForPedal;
  }

  void pause() {
    if (state == WorkoutState.running ||
        state == WorkoutState.waitingForPedal) {
      state = WorkoutState.paused;
      autoPaused = false;
      ramping = false;
    }
  }

  void resume() {
    if (state == WorkoutState.paused) {
      state = WorkoutState.waitingForPedal;
      autoPaused = false;
      _zero = 0;
    }
  }

  void stop() {
    state = WorkoutState.stopped;
    ramping = false;
    autoPaused = false;
    _transitionFrom = null;
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

  void tick(double dt, {required bool connected, required int currentWatts}) {
    if (!dt.isFinite) throw ArgumentError('Non-finite tick');
    dt = math.max(0, dt);
    if (state == WorkoutState.running && (!connected || dt > 5)) {
      state = WorkoutState.paused;
      autoPaused = dt <= 5;
      ramping = false;
      _transitionFrom = null;
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
    dt = math.min(dt, workout.duration - elapsed);
    if (currentWatts <= 0) {
      dt = math.min(dt, math.max(0, 2 - _zero));
      _zero += dt;
    } else {
      _zero = 0;
    }
    elapsed += dt;
    _update(dt);
    if (elapsed >= workout.duration) {
      state = WorkoutState.completed;
    } else if (_zero >= 2) {
      state = WorkoutState.paused;
      autoPaused = true;
      ramping = false;
      _transitionFrom = null;
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
    }
    _lastIndex = blockIndex;
    _lastTarget = targetWatts;
  }
}
