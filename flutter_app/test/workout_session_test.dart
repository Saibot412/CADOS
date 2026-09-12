import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/features/workout/workout_engine.dart';
import 'package:cados_app/features/catalog/records.dart';
import 'package:cados_app/features/session/workout_session_controller.dart';
import 'package:cados_app/features/trainer/ftms_transport.dart';
import 'package:cados_app/features/trainer/ftms_protocol.dart';

import 'session_helpers.dart';
import 'account_test.dart' show record;

import 'package:cados_app/core/device.dart';
import 'package:cados_app/features/heart_rate/heart_rate.dart';

void main() {
  late SessionHarness h;
  setUp(() => h = SessionHarness());
  tearDown(() async => h.close());
  test('HR loss does not pause; missing HR stays null in samples', () async {
    await h.prepare();
    await h.hr.connect(const SensorDevice('hr', 'Garmin'));
    await h.session.start();
    await h.step();
    h.hrTransport.data.add(const HeartRateMeasurement(142));
    await Future<void>.delayed(Duration.zero);
    await h.step();
    expect(h.session.data!.samples.last['heart_rate'], 142);
    h.hrTransport.lost.add(null);
    await Future<void>.delayed(Duration.zero);
    await h.step();
    expect(h.session.state, WorkoutState.running);
    expect(h.session.data!.samples.last['heart_rate'], isNull);
  });
  test(
    'pause failure is visible, suspension gap never advances time',
    () async {
      await h.prepare();
      await h.session.start();
      await h.step();
      await h.step();
      h.transport.failPause = true;
      await h.session.pause();
      expect(h.session.error, isNotNull);
      expect(h.session.state, WorkoutState.paused);
      h.transport.failPause = false;
      await h.session.resume();
      await h.step();
      final elapsed = h.session.engine!.elapsed;
      await h.step(ms: 6000);
      expect(h.session.engine!.elapsed, elapsed);
      expect(h.session.state, WorkoutState.paused);
    },
  );
  test(
    'disconnect during outstanding target cannot release pause latch',
    () async {
      await h.prepare();
      await h.session.start();
      h.transport.powerGate = Completer<void>();
      final tick = h.step();
      await Future<void>.delayed(Duration.zero);
      h.transport.connectionController.add(FtmsConnectionState.disconnected);
      await Future<void>.delayed(Duration.zero);
      h.transport.powerGate!.complete();
      await tick;
      await h.session.tick();
      expect(h.session.state, WorkoutState.paused);
      expect(h.session.engine!.autoPaused, false);
    },
  );
  test(
    'start gates profile/catalog/device; no default FTP or missing workouts',
    () async {
      await h.session.initialize();
      await h.session.start();
      expect(h.transport.starts, 0);
      await h.prepare();
      h.account.catalog = Catalog.fromJson({
        'records': [testCatalog().workouts.single.record.toJson()],
      });
      await h.session.start();
      expect(h.transport.starts, 0);
      expect(h.session.error, contains('FTP'));
    },
  );
  test('waits for new positive power; 1Hz changed-only stepped targets and real samples', () async {
    await h.prepare();
    await h.measurement(180);
    await h.session.start();
    expect(h.transport.starts, 1);
    expect(h.session.state, WorkoutState.waitingForPedal);
    await h.step(watts: null);
    expect(h.session.engine!.elapsed, 0);
    expect(h.transport.sentPower, isEmpty);
    await h.step(watts: 0);
    expect(h.session.state, WorkoutState.waitingForPedal);
    await h.step();
    expect(h.session.state, WorkoutState.running);
    expect(h.session.engine!.elapsed, 0);
    expect(h.transport.sentPower, [50]);
    await h.step(ms: 200);
    expect(h.transport.sentPower, [50]);
    await h.step(ms: 800);
    expect(h.transport.sentPower, [50, 65]);
    expect(h.session.data!.samples.length, 1);
    final s = h.session.data!.samples.single;
    expect(s['duration_sec'], 1);
    expect(s['workout_elapsed_sec'], 0);
    expect(s['watts'], 180);
    expect(s['cadence'], 91.5);
    expect(s['heart_rate'], null);
    expect(s['target_watts'], 50);
    for (var i = 0; i < 8; i++) {
      await h.step();
    }
    final count = h.transport.sentPower.length;
    await h.step();
    expect(h.transport.sentPower.length, count);
    h.session.adjust(5);
    await h.step();
    expect(h.transport.sentPower.last, 205);
    h.session.adjust(1000);
    await h.step();
    expect(h.transport.sentPower.last, 500);
    expect(h.journal.checkpoints, greaterThan(2));
  });
  test('disconnect and stale telemetry latch pause; reconnection needs explicit resume and new power', () async {
    await h.prepare();
    await h.session.start();
    await h.step();
    await h.step();
    h.transport.connectionController.add(FtmsConnectionState.disconnected);
    await Future<void>.delayed(Duration.zero);
    expect(h.session.state, WorkoutState.paused);
    final elapsed = h.session.engine!.elapsed;
    await h.trainer.connect(const FtmsDevice(id: 'trainer', name: 'KICKR'));
    await h.step();
    expect(h.session.state, WorkoutState.paused);
    expect(h.session.engine!.elapsed, elapsed);
    expect(h.transport.starts, 1);
    await h.session.resume();
    await h.step(watts: null);
    expect(h.session.state, WorkoutState.waitingForPedal);
    await h.step();
    expect(h.session.state, WorkoutState.running);
    await h.step(watts: null, ms: 4000);
    expect(h.session.state, WorkoutState.paused);
    expect(h.session.engine!.autoPaused, false);
  });
  test(
    'manual pause/resume/stop and completion finalize exactly once',
    () async {
      await h.prepare(duration: 2);
      await h.session.start();
      await h.step();
      await h.session.pause();
      expect(h.transport.pauses, 1);
      expect(h.session.state, WorkoutState.paused);
      await h.session.resume();
      expect(h.transport.starts, 2);
      await h.step();
      await h.step();
      await h.step();
      expect(h.session.state, WorkoutState.completed);
      expect(h.transport.stops, 1);
      expect(h.journal.finishes, 1);
      await Future.wait([h.session.tick(), h.session.stop(), h.session.stop()]);
      expect(h.transport.stops, 1);
      expect(h.journal.finishes, 1);
      final record = h.journal.outbox.single['record'] as Map;
      final p = record['payload'] as Map;
      expect(record['id'], sessionId);
      expect(record['revision'], 0);
      expect(p['plan_id'], 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d');
      expect(p['user_id'], '395599cb-cc7b-409d-bfef-50d70e8adf8b');
      expect(p['duration_sec'], 2);
      expect(p['status'], 'completed');
    },
  );
  test('FTMS failures never count as success; persistence failure before start sends no command', () async {
    await h.prepare();
    h.journal.fail = true;
    await h.session.start();
    expect(h.transport.starts, 0);
    expect(h.session.state, WorkoutState.paused);
    h.journal.fail = false;
    h.transport.failStart = true;
    await h.session.resume();
    expect(h.session.state, WorkoutState.paused);
    h.transport.failStart = false;
    await h.session.resume();
    h.transport.failPower = true;
    await h.step();
    expect(h.session.state, WorkoutState.paused);
    expect(h.session.error, isNotNull);
    h.transport.failStop = true;
    await h.session.stop();
    expect(h.journal.finishes, 0);
    expect(h.session.hasSession, true);
    h.transport.failStop = false;
    await h.session.stop();
    expect(h.journal.finishes, 1);
  });
  test('background during in-flight start prevents late resume; concurrent stop serialized', () async {
    await h.prepare();
    h.transport.startGate = Completer<void>();
    final start = h.session.start();
    await Future<void>.delayed(Duration.zero);
    final pause = h.session.background();
    h.transport.startGate!.complete();
    await start;
    await pause;
    expect(h.session.state, WorkoutState.paused);
    expect(h.transport.sentPower, isEmpty);
    await Future.wait([h.session.stop(), h.session.stop()]);
    expect(h.transport.stops, 1);
    expect(h.journal.finishes, 1);
  });
  test('failed outbox write retries without another FTMS stop', () async {
    await h.prepare();
    await h.session.start();
    await h.step();
    await h.step();
    h.journal.fail = true;
    await h.session.stop();
    expect(h.transport.stops, 1);
    expect(h.session.hasSession, true);
    expect(h.journal.finishes, 0);
    h.journal.fail = false;
    await h.session.stop();
    expect(h.transport.stops, 1);
    expect(h.journal.finishes, 1);
  });
  test(
    'power range is bounded and steps respect trainer capabilities',
    () async {
      h.transport.powerRange = const FtmsPowerRange(
        minimumWatts: 60,
        maximumWatts: 300,
        incrementWatts: 10,
      );
      await h.prepare();
      await h.session.start();
      await h.step();
      expect(h.transport.sentPower, [60]);
      h.session.adjust(1000);
      for (var i = 0; i < 7; i++) {
        await h.step();
      }
      expect(h.transport.sentPower.last, 300);
      expect(
        h.transport.sentPower.every((p) => (p - 60) % 10 == 0 && p <= 300),
        true,
      );
    },
  );
  test('FTP ramp cadence finish finalizes measured local assessment', () async {
    const workoutId = '165adcb9-77e1-46c3-809b-2c4d2ea50446';
    final payload = {
      'name': 'FTP Ramp Test (ERG)',
      'source_name': 'ftp-ramp.json',
      'blocks': [
        {
          'type': 'steady',
          'label': 'Warmup',
          'duration_sec': 1,
          'target_watts': 500,
        },
        {
          'type': 'steady',
          'label': 'Step 1',
          'duration_sec': 120,
          'target_watts': 100,
        },
      ],
    };
    await h.prepare();
    h.account.catalog = Catalog.fromJson({
      'records': [
        record(workoutId, 'workout', payload),
        record('395599cb-cc7b-409d-bfef-50d70e8adf8b', 'profile', {
          'id': '395599cb-cc7b-409d-bfef-50d70e8adf8b',
          'name': 'Test rider',
          'ftp': 250,
        }),
      ],
    });
    h.session.select(h.account.catalog!.workouts.single);
    await h.session.start();
    await h.step(watts: 180); // Start pedaling; no ridden time yet.
    await h.step(watts: 180); // Warm-up target/power must not affect FTP.
    for (var i = 0; i < 60; i++) {
      await h.step(watts: 300, cadence: 90);
    }
    await h.step(watts: 300, cadence: null);
    expect(h.session.state, WorkoutState.running);
    await h.step(watts: 300, cadence: 0);

    expect(h.session.state, WorkoutState.completed);
    expect(h.transport.stops, 1);
    expect(h.journal.finishes, 1);
    expect(h.session.completedFtpTest, {
      'old_ftp': 250,
      'method': '75_percent_best_continuous_minute',
      'eligible': true,
      'best_minute_watts': 300,
      'estimated_ftp': 225,
    });
    final result = (h.journal.outbox.single['record'] as Map)['payload'] as Map;
    expect(result['workout_elapsed_sec'], 62);
    expect(result['ftp_test_result'], h.session.completedFtpTest);
    expect(result['metrics']['best_minute_watts'], 300);
    expect(result['metrics']['max_watts'], 300);
  });
}
