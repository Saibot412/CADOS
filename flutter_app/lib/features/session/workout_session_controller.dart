import 'dart:async';

import 'package:flutter/foundation.dart';

import '../account/account_controller.dart';
import '../catalog/records.dart';
import '../trainer/trainer_controller.dart';
import '../heart_rate/heart_rate_controller.dart';
import '../workout/workout_engine.dart';
import '../workout/workout_parser.dart';
import 'session_payload.dart';
import 'session_ports.dart';
import 'training_preferences.dart';

part 'workout_selection.dart';

/// Serialized session operations; device events latch pause synchronously even
/// when a Control Point command or checkpoint is in flight.
class WorkoutSessionController extends ChangeNotifier {
  WorkoutSessionController({
    required this.account,
    required this.trainer,
    this.heartRate,
    required this.journal,
    required this.clock,
    required this.ticker,
    this.onFinalized,
    this.trainingPreferences,
    String Function()? newId,
  }) : newId = newId ?? sessionUuid {
    trainer.addListener(_deviceChanged);
    account.addListener(_accountChanged);
    heartRate?.addListener(_changed);
  }
  final AccountController account;
  final TrainerController trainer;
  final HeartRateController? heartRate;
  final SessionJournal journal;
  final SessionClock clock;
  final SessionTicker ticker;
  final String Function() newId;
  final Future<void> Function()? onFinalized;
  final TrainingPreferences? trainingPreferences;
  WorkoutRecord? selected;
  String? planId, error;
  WorkoutEngine? engine;
  SessionData? data, recovery;
  bool initialized = false,
      busy = false,
      adaptiveErgPreferred = false,
      _closed = false,
      _safetyQueued = false;
  bool _stopConfirmed = false, _completionPending = false;
  bool _shuttingDown = false;
  Map<String, dynamic>? _finalEntry;
  Map<String, num>? completedMetrics;
  Map<String, dynamic>? completedFtpTest;
  Duration? _lastTick, _lastTargetAt, _lastCheckpoint;
  int? _lastTarget;
  int _afterSequence = 0, _pauseGeneration = 0;
  Future<void> _tail = Future.value();
  bool get active => data != null && _finalEntry == null;
  bool get hasSession => data != null;
  Map<String, num>? get metrics =>
      data?.metrics.summary(data!.ftp) ?? completedMetrics;
  bool get canSelect => !hasSession && recovery == null && initialized && !busy;
  WorkoutState get state => engine?.state ?? WorkoutState.ready;
  int? get watts =>
      _fresh(trainer.lastMeasurementAt) ? trainer.measurement.powerWatts : null;
  double? get cadence =>
      _fresh(trainer.lastMeasurementAt) ? trainer.measurement.cadenceRpm : null;
  int? get bpm =>
      heartRate?.measurement != null && _fresh(heartRate?.lastMeasurementAt)
      ? heartRate!.measurement!.bpm
      : null;
  bool _fresh(DateTime? at) =>
      at != null &&
      clock.now().difference(at).inMilliseconds >= 0 &&
      clock.now().difference(at) <= const Duration(seconds: 3);
  int? get target => state == WorkoutState.running ? _lastTarget : null;
  int? get prescribedTarget => state == WorkoutState.running && engine != null
      ? _clamp(engine!.targetWatts)
      : null;
  int? get effectiveTrainerTarget => engine == null ? null : _lastTarget;
  int get adaptiveReliefWatts {
    final current = engine;
    if (current == null) return 0;
    final difference =
        _clamp(current.targetWatts) - _clamp(current.trainerTargetWatts);
    return difference > 0 ? difference : 0;
  }

  bool get adaptiveErgActive => engine?.adaptiveErgEnabled ?? false;
  bool get adaptiveErgAllowed {
    final current = engine;
    if (current != null) return !current.isFtpTest;
    final name = selected?.name.toLowerCase() ?? '';
    return !(name.contains('ftp') && name.contains('ramp'));
  }

  int _clamp(int watts) =>
      (trainer.powerRange?.clampAndRound(watts) ?? watts).clamp(0, 32767);
  void _changed() {
    if (!_closed) notifyListeners();
  }

  Future<void> _run(Future<void> Function() action) {
    if (_closed || _shuttingDown) return Future.value();
    final result = _tail.then((_) async {
      if (_closed || _shuttingDown) return;
      busy = true;
      _changed();
      try {
        await action();
      } catch (e) {
        final moving =
            state == WorkoutState.running ||
            state == WorkoutState.waitingForPedal;
        engine?.pause();
        if (engine != null) engine!.autoPaused = false;
        if (moving) await _pauseHardware();
        error = e is FormatException ? e.message : 'Training konnte nicht sicher ausgeführt oder gespeichert werden. Bitte erneut versuchen.';
      } finally {
        busy = false;
        _changed();
      }
    });
    _tail = result;
    return result;
  }

  Future<void> initialize() => _run(() async {
    final stored = await journal.load();
    if (stored.draft != null) recovery = SessionData.restore(stored.draft!);
    try {
      adaptiveErgPreferred =
          await trainingPreferences?.readAdaptiveErg() ?? false;
    } catch (_) {
      adaptiveErgPreferred = false;
      error = 'Adaptive-ERG-Einstellung konnte nicht geladen werden.';
    }
    initialized = true;
    ticker.start(() {
      if (!busy) unawaited(tick());
    });
  });
  Future<void> start() => _run(() async {
    if (hasSession) return;
    if (readiness != null) throw FormatException(readiness!);
    final current = account.catalog!.workouts
        .where((w) => w.record.id == selected!.record.id)
        .toList();
    if (current.length != 1) {
      throw const FormatException(
        'Workout wurde entfernt. Bitte neu auswählen.',
      );
    }
    final profile = _profile;
    if (planId != null &&
        !account.catalog!
            .upcoming(clock.now().toLocal())
            .any(
              (p) =>
                  sameUuid(p.record.id, planId!) &&
                  sameUuid(p.workoutId, current.single.record.id),
            )) {
      throw const FormatException('Geplante Einheit ist nicht mehr verfügbar.');
    }
    selected = current.single;
    final parsed = WorkoutParser.parse(
      selected!.record.payload,
      ftp: profile.ftp!,
    );
    engine = WorkoutEngine(parsed);
    engine!.setAdaptiveErg(adaptiveErgPreferred);
    data = SessionData(
      id: newId(),
      server: account.config.base.toString(),
      accountId: account.user!.id,
      workoutId: selected!.record.id,
      workoutPayload: copyJson(selected!.record.payload),
      profile: {...copyJson(profile.record.payload), 'id': profile.record.id},
      ftp: profile.ftp!,
      startedAt: clock.now().toUtc().toIso8601String(),
      planId: planId,
    );
    _stopConfirmed = false;
    _completionPending = false;
    _finalEntry = null;
    completedMetrics = null;
    completedFtpTest = null;
    engine!.start();
    engine!.pause();
    await _checkpoint(); // Must be durable before any trainer command.
    await _resume();
  });
  Future<void> resume() => _run(_resume);
  Future<void> _resume() async {
    if (data == null ||
        _finalEntry != null ||
        _completionPending ||
        state != WorkoutState.paused) {
      return;
    }
    if (readiness != null) throw FormatException(readiness!);
    await _checkpoint();
    final generation = _pauseGeneration;
    if (!await trainer.startTraining()) {
      throw FormatException(trainer.error ?? 'Trainerstart fehlgeschlagen.');
    }
    if (!trainer.connected ||
        _closed ||
        _shuttingDown ||
        generation != _pauseGeneration ||
        account.user?.id != data?.accountId ||
        account.config.base.toString() != data?.server) {
      await _pauseHardware();
      return;
    }
    engine!.resume();
    _afterSequence = trainer.measurementSequence;
    _lastTick = clock.monotonic;
    _lastTarget = null; // Throttle still spans pause/resume.
    error = null;
    await _checkpoint();
  }

  Future<void> pause() {
    _latch();
    return _run(() async {
      await _pauseHardware();
      await _checkpoint();
    });
  }

  void _latch() {
    if (data == null || _finalEntry != null) return;
    _pauseGeneration++;
    if (state == WorkoutState.running ||
        state == WorkoutState.waitingForPedal) {
      data!.segment++;
    }
    engine?.pause();
    engine?.autoPaused = false;
    _lastTick = clock.monotonic;
    _changed();
  }

  Future<void> _pauseHardware() async {
    if (trainer.connected && !await trainer.pauseTraining()) {
      error = trainer.error ?? 'Trainerpause nicht bestätigt.';
    }
  }

  void _deviceChanged() {
    if (active &&
        !trainer.connected &&
        (state == WorkoutState.running ||
            state == WorkoutState.waitingForPedal)) {
      _safety(
        'Trainerverbindung unterbrochen. Erneutes Fortsetzen erforderlich.',
      );
    }
    _changed();
  }

  void _accountChanged() {
    if (active &&
        (account.user?.id != data!.accountId ||
            account.config.base.toString() != data!.server)) {
      _safety(
        'Konto geändert. Mit ursprünglichem Konto anmelden und ausdrücklich fortsetzen.',
      );
    }
    _changed();
  }

  void _safety(String message) {
    _latch();
    error = message;
    if (_safetyQueued) return;
    _safetyQueued = true;
    unawaited(
      _run(() async {
        try {
          await _pauseHardware();
          await _checkpoint();
        } finally {
          _safetyQueued = false;
        }
      }),
    );
  }

  Future<void> tick() => _run(() async {
    if (!active || engine == null) return;
    final now = clock.monotonic;
    final dt = _lastTick == null
        ? 0.0
        : (now - _lastTick!).inMicroseconds / 1000000;
    if (dt < 1) return;
    _lastTick = now;
    if (state == WorkoutState.running ||
        state == WorkoutState.waitingForPedal) {
      if (!trainer.connected ||
          dt > 5 ||
          (state == WorkoutState.running && watts == null)) {
        _latch();
        error = 'Leistungsdaten fehlen oder wurden unterbrochen. Bitte ausdrücklich fortsetzen.';
        await _pauseHardware();
        await _checkpoint();
        return;
      }
      if (state == WorkoutState.waitingForPedal &&
          (trainer.measurementSequence <= _afterSequence || watts == null)) {
        if (_lastCheckpoint == null ||
            now - _lastCheckpoint! >= const Duration(seconds: 5)) {
          await _checkpoint();
        }
        return;
      }
      final before = engine!.elapsed;
      final wasRunning = state == WorkoutState.running;
      final previousTarget = _lastTarget;
      final block = engine!.blockIndex;
      engine!.tick(
        dt,
        connected: trainer.connected,
        currentWatts: watts!,
        currentCadence: cadence,
      );
      final advanced = engine!.elapsed - before;
      if (wasRunning && advanced > 0 && previousTarget != null) {
        data!.sample(
          duration: advanced,
          from: before,
          watts: watts!.clamp(0, 32767),
          cadence: cadence,
          hr: bpm,
          target: previousTarget,
          block: block,
        );
      }
      if (state == WorkoutState.completed) {
        _completionPending = true;
        await _finish('completed');
        return;
      }
      if (state == WorkoutState.paused) {
        engine!.autoPaused = false;
        data!.segment++;
        await _pauseHardware();
        await _checkpoint();
        return;
      }
      if (state == WorkoutState.running) {
        final target = _clamp(engine!.trainerTargetWatts);
        if (target != _lastTarget &&
            (_lastTargetAt == null ||
                now - _lastTargetAt! >= const Duration(seconds: 1))) {
          _lastTargetAt = now;
          if (!await trainer.setPower(target)) {
            _latch();
            error = trainer.error ?? 'Zielleistung nicht bestätigt.';
            await _pauseHardware();
            await _checkpoint();
            return;
          }
          _lastTarget = target;
          if (engine!.adaptiveErgEnabled && adaptiveReliefWatts > 0) {
            trainer.logger?.log(
              'Adaptive ERG target: prescribed=${_clamp(engine!.targetWatts)}W '
              'effective=${target}W relief=${adaptiveReliefWatts}W',
            );
          }
        }
      }
    }
    if (_lastCheckpoint == null ||
        now - _lastCheckpoint! >= const Duration(seconds: 5)) {
      await _checkpoint();
    }
  });
  Future<void> stop() {
    _latch();
    return _run(() => _finish(_completionPending ? 'completed' : 'stopped'));
  }

  Future<void> _finish(String status) async {
    if (data == null) return;
    if (!_stopConfirmed) {
      if (!await trainer.stopTraining()) {
        _latch();
        error = trainer.error ?? 'Stop nicht bestätigt. Bitte erneut stoppen.';
        await _checkpoint();
        return;
      }
      _stopConfirmed = true;
    }
    _capture();
    _finalEntry ??= copyJson(data!.finalize(status, clock.now()));
    await journal.finalize(_finalEntry!);
    final payload = (_finalEntry!['record'] as Map)['payload'] as Map;
    completedMetrics = Map<String, num>.from(payload['metrics'] as Map);
    completedFtpTest = payload['ftp_test_result'] == null
        ? null
        : Map<String, dynamic>.from(payload['ftp_test_result'] as Map);
    engine!.stop();
    if (status == 'completed') engine!.state = WorkoutState.completed;
    data = null;
    _finalEntry = null;
    error = null;
    if (onFinalized != null) unawaited(onFinalized!());
  }

  void adjust(int delta) {
    if (active) {
      engine?.adjustTarget(delta);
      _changed();
    }
  }

  Future<void> setAdaptiveErg(bool enabled) => _run(() async {
    await trainingPreferences?.saveAdaptiveErg(enabled);
    adaptiveErgPreferred = enabled;
    engine?.setAdaptiveErg(enabled);
    trainer.logger?.log(
      'Adaptive ERG preference: ${enabled ? 'enabled' : 'disabled'}; '
      'active=$adaptiveErgActive ftp_test=${engine?.isFtpTest ?? false}',
    );
    if (state == WorkoutState.running && engine != null) {
      final effective = _clamp(engine!.trainerTargetWatts);
      if (effective != _lastTarget) {
        if (!await trainer.setPower(effective)) {
          _latch();
          error =
              trainer.error ?? 'Adaptive ERG konnte nicht bestätigt werden.';
          await _pauseHardware();
          await _checkpoint();
          return;
        }
        _lastTarget = effective;
        _lastTargetAt = clock.monotonic;
      }
    }
    if (active) await _checkpoint();
  });

  void _capture() {
    if (data != null && engine != null) {
      data!.elapsed = engine!.elapsed;
      data!.adjustment = engine!.adjustment;
    }
  }

  Future<void> _checkpoint() async {
    _capture();
    if (data != null) {
      await journal.checkpoint(data!.draft());
      _lastCheckpoint = clock.monotonic;
    }
  }

  Future<void> recover() => _run(() async {
    if (recovery == null || data != null) return;
    data = recovery;
    recovery = null;
    engine = WorkoutEngine(
      WorkoutParser.parse(data!.workoutPayload, ftp: data!.ftp),
    );
    engine!.setAdaptiveErg(adaptiveErgPreferred);
    engine!.elapsed = data!.elapsed;
    engine!.adjustment = data!.adjustment;
    engine!.restoreFtpCadenceSeen(data!.samples);
    engine!.state = WorkoutState.paused;
    data!.segment++;
    _lastTick = clock.monotonic;
    _completionPending = data!.elapsed >= engine!.workout.duration;
    planId = data!.planId;
    error = 'Einheit wiederhergestellt und pausiert. Trainer verbinden und ausdrücklich fortsetzen.';
    await _checkpoint();
  });
  Future<void> discardRecovery() => _run(() async {
    if (data != null) return;
    await journal.discard();
    recovery = null;
    error = null;
  });
  Future<void> background() => hasSession ? pause() : Future.value();
  Future<void> shutdown() async {
    if (_shuttingDown) {
      await _tail;
      return;
    }
    _shuttingDown = true;
    ticker.cancel();
    _latch();
    await _tail;
    try {
      if (data != null) {
        await _pauseHardware();
        await _checkpoint();
      }
    } catch (_) {
      error = 'Sicherung beim Beenden fehlgeschlagen; letzte Sicherung bleibt erhalten.';
    }
    _closed = true;
    trainer.removeListener(_deviceChanged);
    account.removeListener(_accountChanged);
    heartRate?.removeListener(_changed);
  }

  @override
  void dispose() {
    ticker.cancel();
    trainer.removeListener(_deviceChanged);
    account.removeListener(_accountChanged);
    heartRate?.removeListener(_changed);
    _closed = true;
    super.dispose();
  }
}
