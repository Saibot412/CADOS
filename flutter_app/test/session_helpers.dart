import 'dart:async';

import 'package:cados_app/features/account/account_controller.dart';
import 'package:cados_app/features/catalog/records.dart';
import 'package:cados_app/features/session/session_payload.dart';
import 'package:cados_app/features/session/session_ports.dart';
import 'package:cados_app/features/session/workout_session_controller.dart';
import 'package:cados_app/features/session/session_sync_controller.dart';
import 'package:cados_app/features/trainer/trainer_controller.dart';
import 'package:cados_app/features/trainer/ftms_protocol.dart';
import 'package:cados_app/features/trainer/ftms_transport.dart';

import 'account_test.dart' show TestHttp, TestStore, testUser, record;
import 'fake_trainer_transport.dart';
import 'heart_rate_controller_test.dart'
    show FakeHr, MemoryLog, MemoryPreferences;

import 'package:cados_app/features/heart_rate/heart_rate_controller.dart';

const sessionId = 'f67322a9-685e-4f8b-9506-c0443d7f6ab1';
Map<String, dynamic> workoutPayload({int duration = 20}) => {
  'name': 'Server workout',
  'source_name': 'real.json',
  'description': 'From sync',
  'extension': {'retain': true},
  'blocks': [
    {
      'type': 'steady',
      'duration_sec': duration,
      'target_pct_ftp': 0.8,
      'target_cadence': 90,
    },
  ],
};
Catalog testCatalog({int duration = 20}) => Catalog.fromJson({
  'records': [
    record(
      '065adcb9-77e1-46c3-809b-2c4d2ea50446',
      'workout',
      workoutPayload(duration: duration),
    ),
    record('395599cb-cc7b-409d-bfef-50d70e8adf8b', 'profile', {
      'id': '395599cb-cc7b-409d-bfef-50d70e8adf8b',
      'name': 'Test rider',
      'ftp': 250,
    }),
    record('ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d', 'plan', {
      // Keep the UI fixture upcoming instead of expiring with wall-clock time.
      'date': DateTime.now()
          .add(const Duration(days: 1))
          .toIso8601String()
          .substring(0, 10),
      'workout_id': '065adcb9-77e1-46c3-809b-2c4d2ea50446',
      'workout_name': 'Server workout',
    }),
  ],
});

class TestClock implements SessionClock {
  Duration time = Duration.zero;
  @override
  DateTime now() => DateTime.utc(2026, 9, 11).add(time);
  @override
  Duration get monotonic => time;
  void advance([int milliseconds = 1000]) {
    time += Duration(milliseconds: milliseconds);
  }
}

class TestTicker implements SessionTicker {
  void Function()? callback;
  @override
  void start(void Function() value) {
    callback = value;
  }

  @override
  void cancel() {
    callback = null;
  }
}

class TestJournal implements SessionJournal {
  Map<String, dynamic>? draft;
  List<Map<String, dynamic>> outbox = [];
  bool fail = false;
  int checkpoints = 0, finishes = 0;
  @override
  Future<JournalState> load() async => JournalState(draft, outbox);
  @override
  Future<void> checkpoint(Map<String, dynamic> value) async {
    if (fail) throw StateError('disk');
    draft = copyJson(value);
    checkpoints++;
  }

  @override
  Future<void> discard() async {
    draft = null;
  }

  @override
  Future<void> finalize(Map<String, dynamic> entry) async {
    if (fail) throw StateError('disk');
    outbox.add(copyJson(entry));
    draft = null;
    finishes++;
  }

  @override
  Future<void> acknowledge(String id) async {
    outbox.removeWhere((e) => (e['record'] as Map)['id'] == id);
  }
}

class TestUploader implements SessionUploader {
  bool fail = false;
  final entries = <Map<String, dynamic>>[];
  @override
  Future<void> upload(Map<String, dynamic> e) async {
    if (fail) throw StateError('offline');
    entries.add(e);
  }
}

class SessionTrainer extends FakeTrainerTransport {
  int starts = 0, pauses = 0, stops = 0;
  bool failStart = false,
      failPower = false,
      failPause = false,
      failStop = false;
  Completer<void>? startGate, powerGate;
  FtmsControlResponse response(bool failure) =>
      FtmsControlResponse(requestOpcode: 7, resultCode: failure ? 4 : 1);
  @override
  Future<FtmsControlResponse> startTraining() async {
    starts++;
    await startGate?.future;
    return response(failStart);
  }

  @override
  Future<FtmsControlResponse> pauseTraining() async {
    pauses++;
    return response(failPause);
  }

  @override
  Future<FtmsControlResponse> stopTraining() async {
    stops++;
    return response(failStop);
  }

  @override
  Future<FtmsControlResponse> setTargetPower(int watts) async {
    sentPower.add(watts);
    await powerGate?.future;
    return response(failPower);
  }
}

class SessionHarness {
  SessionHarness() {
    account = AccountController(http, store, store);
    trainer = TrainerController(transport, now: clock.now);
    hr = HeartRateController(
      hrTransport,
      MemoryLog(),
      MemoryPreferences(),
      now: clock.now,
    );
    session = WorkoutSessionController(
      heartRate: hr,
      account: account,
      trainer: trainer,
      journal: journal,
      clock: clock,
      ticker: ticker,
      newId: () => sessionId,
    );
    sync = SessionSyncController(
      account: account,
      journal: journal,
      uploader: TestUploader(),
    );
  }
  final hrTransport = FakeHr();
  late final HeartRateController hr;
  final clock = TestClock(),
      ticker = TestTicker(),
      journal = TestJournal(),
      http = TestHttp(),
      store = TestStore(),
      transport = SessionTrainer();
  late final AccountController account;
  late final TrainerController trainer;
  late final WorkoutSessionController session;
  late final SessionSyncController sync;
  Future<void> prepare({int duration = 20}) async {
    http.json({'token': 'test-only-token', 'user': testUser});
    http.json({
      'records': testCatalog(duration: duration).records
          .map((r) => r.toJson())
          .toList(),
    });
    await account.login('rider@example.invalid', 'test-only-password');
    await session.initialize();
    await trainer.connect(const FtmsDevice(id: 'trainer', name: 'KICKR'));
    session.select(
      account.catalog!.workouts.single,
      plan: 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d',
    );
  }

  Future<void> measurement(int watts, {double? cadence = 91.5}) async {
    transport.measurementController.add(
      IndoorBikeMeasurement(powerWatts: watts, cadenceRpm: cadence),
    );
    await Future<void>.delayed(Duration.zero);
  }

  Future<void> step({
    int? watts = 180,
    int ms = 1000,
    double? cadence = 91.5,
  }) async {
    clock.advance(ms);
    if (watts != null) await measurement(watts, cadence: cadence);
    await session.tick();
  }

  Future<void> close() async {
    await session.shutdown();
    session.dispose();
    sync.dispose();
    await sync.closed;
    account.dispose();
    hr.dispose();
    await hr.closed;
    trainer.dispose();
    await trainer.closed;
  }
}
