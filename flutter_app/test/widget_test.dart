import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/presentation/cados_app.dart';
import 'package:cados_app/features/workout/workout_engine.dart';

import 'session_helpers.dart';

import 'package:cados_app/features/trainer/ftms_protocol.dart';

void main() {
  testWidgets(
    'real catalog plan selection, readiness, measured values and start control',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final h = SessionHarness();
      await h.prepare();
      await tester.pumpWidget(
        CadosApp(
          account: h.account,
          controller: h.trainer,
          session: h.session,
          sync: h.sync,
        ),
      );
      final planDate = h.account.catalog!.upcoming(DateTime.now()).single.date;
      await tester.tap(find.byKey(Key('calendarDay-$planDate')));
      await tester.pumpAndSettle();
      final prepare = find.text('Vorbereiten').first;
      await tester.ensureVisible(prepare);
      await tester.tap(prepare);
      await tester.pumpAndSettle();
      expect(h.session.planId, 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d');
      expect(
        find.text('Mit geplanter Kalendereinheit verknüpft'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('power100')), findsNothing);
      expect(find.text('0 W'), findsNothing);
      await tester.tap(find.byKey(const Key('startWorkout')));
      await tester.pumpAndSettle();
      expect(h.transport.starts, 1);
      expect(h.session.state, WorkoutState.waitingForPedal);
      h.clock.advance();
      h.transport.measurementController.add(
        const IndoorBikeMeasurement(powerWatts: 247, cadenceRpm: 91.5),
      );
      await tester.pump();
      await h.session.tick();
      await tester.pumpAndSettle();
      expect(find.text('247 W'), findsOneWidget);
      expect(find.text('91.5 rpm'), findsOneWidget);
      h.clock.advance();
      h.transport.measurementController.add(
        const IndoorBikeMeasurement(powerWatts: 247, cadenceRpm: 91.5),
      );
      await tester.pump();
      await h.session.tick();
      await tester.pumpAndSettle();
      expect(find.text('Trainingsmetriken'), findsOneWidget);
      expect(find.text('Ø Leistung'), findsOneWidget);
      expect(find.text('Normalized Power'), findsOneWidget);
      expect(find.text('247 W'), findsNWidgets(4));
      expect(find.text('0.2 kJ'), findsOneWidget);
      expect(h.transport.sentPower, [50, 65]);
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
    },
  );
}
