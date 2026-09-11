import 'package:cados_ftms_spike/features/trainer/ftms_protocol.dart';
import 'package:cados_ftms_spike/features/trainer/ftms_spike_controller.dart';
import 'package:cados_ftms_spike/features/trainer/ftms_transport.dart';
import 'package:cados_ftms_spike/presentation/ftms_spike_app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_trainer_transport.dart';

void main() {
  testWidgets(
    'shows device, telemetry and enables safe controls after connect',
    (tester) async {
      final transport = FakeTrainerTransport();
      final controller = FtmsSpikeController(transport);
      await tester.pumpWidget(CadosFtmsSpike(controller: controller));

      expect(find.text('CADOS · FTMS Trainer-Test'), findsOneWidget);
      expect(find.text('Nicht verbunden'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('power100')))
            .onPressed,
        isNull,
      );

      transport.scanController.add(
        const FtmsDevice(
          id: 'trainer-1',
          name: 'Test KICKR',
          rssi: -42,
          advertisesFtms: true,
        ),
      );
      await tester.pump();
      expect(find.text('Test KICKR'), findsOneWidget);

      await tester.tap(find.text('Verbinden'));
      await tester.pumpAndSettle();
      expect(find.text('ERG bereit'), findsOneWidget);

      transport.measurementController.add(
        const IndoorBikeMeasurement(powerWatts: 247, cadenceRpm: 91.5),
      );
      await tester.pump();
      expect(controller.measurement.powerWatts, 247);
      await tester.drag(find.byType(ListView).first, const Offset(0, -450));
      await tester.pumpAndSettle();
      expect(find.text('247 W'), findsOneWidget);
      expect(find.text('91.5 rpm'), findsOneWidget);

      await tester.tap(find.byKey(const Key('power100')));
      await tester.pumpAndSettle();
      expect(transport.sentPower, [100]);
    },
  );
}
