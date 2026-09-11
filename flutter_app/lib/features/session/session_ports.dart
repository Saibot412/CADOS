import 'dart:async';

abstract interface class SessionClock {
  DateTime now();
  Duration get monotonic;
}

abstract interface class SessionTicker {
  void start(void Function() callback);
  void cancel();
}

abstract interface class SessionJournal {
  Future<JournalState> load();
  Future<void> checkpoint(Map<String, dynamic> draft);
  Future<void> discard();
  Future<void> finalize(Map<String, dynamic> entry);
  Future<void> acknowledge(String id);
}

class JournalState {
  const JournalState(this.draft, this.outbox);
  final Map<String, dynamic>? draft;
  final List<Map<String, dynamic>> outbox;
}

abstract interface class SessionUploader {
  Future<void> upload(Map<String, dynamic> entry);
}

class SystemSessionClock implements SessionClock {
  final _watch = Stopwatch()..start();
  @override
  DateTime now() => DateTime.now().toUtc();
  @override
  Duration get monotonic => _watch.elapsed;
}

class PeriodicSessionTicker implements SessionTicker {
  Timer? _timer;
  @override
  void start(void Function() callback) {
    cancel();
    _timer = Timer.periodic(
      const Duration(milliseconds: 200),
      (_) => callback(),
    );
  }

  @override
  void cancel() {
    _timer?.cancel();
    _timer = null;
  }
}
