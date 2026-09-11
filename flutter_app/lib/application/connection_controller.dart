import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/device.dart';

/// Serializes attempts; generation invalidation makes cancellation win over late completion.
class ConnectionController extends ChangeNotifier {
  ConnectionController({
    required this.open,
    required this.close,
    required this.log,
    this.maxAttempts = 5,
  });
  final Future<void> Function(SensorDevice) open;
  final Future<void> Function() close;
  final void Function(String) log;
  final int maxAttempts;
  ConnectionPhase phase = ConnectionPhase.idle;
  SensorDevice? selected;
  String? error;
  Timer? _timer;
  int _generation = 0, _attempt = 0;
  bool _disposed = false, _opening = false, _wanted = false;
  bool _lostWhileOpening = false;
  Future<void>? _inflight;
  void _state(ConnectionPhase value) {
    if (_disposed) return;
    phase = value;
    log('Connection ${selected?.name ?? ""}: ${value.name}');
    notifyListeners();
  }

  Future<void> connect(SensorDevice device) async {
    final cancelling = disconnect();
    final generation = _generation;
    await cancelling;
    if (_disposed || generation != _generation) return;
    selected = device;
    _wanted = true;
    _attempt = 0;
    await _startAttempt(_generation);
  }

  Future<void> _startAttempt(int generation) async {
    if (_disposed || !_wanted || generation != _generation || _opening) return;
    final future = _runAttempt(generation);
    _inflight = future;
    await future;
  }

  Future<void> _runAttempt(int generation) async {
    _opening = true;
    _lostWhileOpening = false;
    _state(
      _attempt == 0 ? ConnectionPhase.connecting : ConnectionPhase.reconnecting,
    );
    try {
      await open(selected!);
      if (_disposed || generation != _generation) {
        await close();
        return;
      }
      if (_lostWhileOpening) {
        await close();
        throw StateError('Connection lost during setup');
      }
      error = null;
      _attempt = 0;
      _state(ConnectionPhase.connected);
    } catch (e) {
      if (generation == _generation && !_disposed) {
        error = '$e';
        log('Connection failed: $e');
        _schedule();
      }
    } finally {
      _opening = false;
    }
  }

  void lost() {
    if (!_wanted || _disposed) return;
    if (_opening) {
      _lostWhileOpening = true;
      return;
    }
    _schedule();
  }

  void _schedule() {
    if (_timer != null || !_wanted || _disposed) return;
    if (_attempt >= maxAttempts) {
      _state(ConnectionPhase.failed);
      return;
    }
    _state(ConnectionPhase.reconnecting);
    final generation = _generation;
    final seconds = 1 << _attempt++;
    _timer = Timer(Duration(seconds: seconds), () {
      _timer = null;
      unawaited(_startAttempt(generation));
    });
  }

  Future<void> disconnect() async {
    _wanted = false;
    _generation++;
    _timer?.cancel();
    _timer = null;
    _state(ConnectionPhase.idle);
    await _inflight;
    try {
      await close();
    } catch (e) {
      error = '$e';
      log('Disconnect failed: $e');
    }
  }

  Future<void> shutdown() async {
    await _inflight;
    try {
      await close();
    } catch (e) {
      log('Shutdown: $e');
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _wanted = false;
    _generation++;
    _timer?.cancel();
    super.dispose();
  }
}
