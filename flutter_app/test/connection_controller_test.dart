import 'dart:async';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/application/connection_controller.dart';
import 'package:cados_app/core/device.dart';

void main() {
  const device = SensorDevice('1', 'sensor');
  test(
    'bounded exponential backoff, duplicate loss, explicit cancellation',
    () {
      fakeAsync((clock) {
        var attempts = 0;
        final c = ConnectionController(
          open: (_) async {
            attempts++;
            throw StateError('off');
          },
          close: () async {},
          log: (_) {},
          maxAttempts: 3,
        );
        c.connect(device);
        clock.flushMicrotasks();
        expect(attempts, 1);
        expect(c.phase, ConnectionPhase.reconnecting);
        c.lost();
        c.lost();
        clock.elapse(const Duration(seconds: 1));
        expect(attempts, 2);
        clock.elapse(const Duration(seconds: 2));
        expect(attempts, 3);
        clock.elapse(const Duration(seconds: 4));
        expect(attempts, 4);
        expect(c.phase, ConnectionPhase.failed);
        c.disconnect();
        clock.flushMicrotasks();
        clock.elapse(const Duration(minutes: 1));
        expect(attempts, 4);
        c.dispose();
      });
    },
  );
  test('successful reconnect does not replay commands', () {
    fakeAsync((clock) {
      var attempts = 0;
      final c = ConnectionController(
        open: (_) async {
          attempts++;
        },
        close: () async {},
        log: (_) {},
      );
      c.connect(device);
      clock.flushMicrotasks();
      expect(c.phase, ConnectionPhase.connected);
      c.lost();
      c.lost();
      clock.elapse(const Duration(seconds: 1));
      expect(attempts, 2);
      expect(c.phase, ConnectionPhase.connected);
      c.lost();
      c.dispose();
      clock.elapse(const Duration(minutes: 1));
      expect(attempts, 2);
    });
  });
  test('cancel during setup invalidates late success', () async {
    final setup = Completer<void>();
    var closes = 0;
    final c = ConnectionController(
      open: (_) => setup.future,
      close: () async {
        closes++;
      },
      log: (_) {},
    );
    final connecting = c.connect(device);
    await Future<void>.delayed(Duration.zero);
    final cancelling = c.disconnect();
    setup.complete();
    await connecting;
    await cancelling;
    expect(c.phase, ConnectionPhase.idle);
    expect(closes, greaterThanOrEqualTo(2));
    c.dispose();
  });
  test('loss during setup cannot publish false connected', () async {
    final setup = Completer<void>();
    var closes = 0;
    final c = ConnectionController(
      open: (_) => setup.future,
      close: () async {
        closes++;
      },
      log: (_) {},
    );
    final connecting = c.connect(device);
    await Future<void>.delayed(Duration.zero);
    c.lost();
    setup.complete();
    await connecting;
    expect(c.phase, ConnectionPhase.reconnecting);
    expect(closes, greaterThanOrEqualTo(2));
    await c.disconnect();
    c.dispose();
  });
}
