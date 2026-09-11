import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:cados_ftms_spike/infrastructure/ble/scan_coordinator.dart';

void main() {
  test(
    'exclusive ownership and cancellation during async scan startup',
    () async {
      final started = Completer<void>();
      var stops = 0;
      final scan = ScanCoordinator(
        startScan: (_) => started.future,
        stopScan: () async {
          stops++;
        },
      );
      final trainer = Object(), hr = Object();
      final starting = scan.start(trainer, '1826');
      await expectLater(scan.start(hr, '180d'), throwsStateError);
      await scan.stop(hr);
      expect(stops, 0);
      final stopping = scan.stop(trainer);
      expect(stops, 0);
      started.complete();
      await starting;
      await stopping;
      expect(stops, 1);
      await scan.start(hr, '180d');
      await scan.stop(hr);
      expect(stops, 2);
    },
  );
}
