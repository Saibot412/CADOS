import 'dart:async';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cados_ftms_spike/core/device.dart';
import 'package:cados_ftms_spike/features/trainer/ftms_spike_controller.dart';
import 'package:cados_ftms_spike/features/trainer/ftms_transport.dart';

import 'fake_trainer_transport.dart';

class DelayedTrainer extends FakeTrainerTransport {
  int attempts = 0;
  Completer<void>? setup;
  @override
  Future<void> connect(FtmsDevice device) async {
    attempts++;
    await setup?.future;
    await super.connect(device);
  }
}

void main() {
  test('trainer reconnect waits for ready and never replays power', () {
    fakeAsync((clock) {
      final t = DelayedTrainer();
      final c = FtmsSpikeController(t);
      c.connect(const FtmsDevice(id: 't', name: 'KICKR'));
      clock.flushMicrotasks();
      c.setPower(100);
      clock.flushMicrotasks();
      expect(t.sentPower, [100]);
      t.setup = Completer<void>();
      t.connectionController.add(FtmsConnectionState.disconnected);
      clock.flushMicrotasks();
      expect(c.connected, false);
      expect(c.connection.phase, ConnectionPhase.reconnecting);
      clock.elapse(const Duration(seconds: 1));
      expect(t.attempts, 2);
      expect(c.connected, false);
      c.setPower(200);
      clock.flushMicrotasks();
      expect(t.sentPower, [100]);
      t.setup!.complete();
      clock.flushMicrotasks();
      expect(c.connected, true);
      expect(t.sentPower, [100]);
      c.dispose();
      clock.flushMicrotasks();
    });
  });
}
