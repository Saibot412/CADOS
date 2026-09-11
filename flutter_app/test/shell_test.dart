import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/presentation/cados_app.dart';

import 'account_test.dart' show testUser;
import 'session_helpers.dart';

void main() {
  for (final wide in [false, true]) {
    testWidgets(
      'truthful shell and navigation ${wide ? 'desktop' : 'mobile'}',
      (tester) async {
        tester.view.physicalSize = Size(wide ? 1200 : 600, 1000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final h = SessionHarness();
        final http = h.http, account = h.account;
        await h.session.initialize();
        await tester.pumpWidget(
          CadosApp(
            account: account,
            controller: h.trainer,
            session: h.session,
            sync: h.sync,
          ),
        );
        expect(
          find.text(
            'Bitte in Einstellungen anmelden, um deine CADOS-Daten zu laden.',
          ),
          findsOneWidget,
        );
        expect(
          find.byType(wide ? NavigationRail : NavigationBar),
          findsOneWidget,
        );
        await tester.tap(find.text('Training').last);
        await tester.pumpAndSettle();
        expect(find.text('Trainer: Nicht verbunden'), findsOneWidget);
        expect(find.text('0 W'), findsNothing);
        expect(find.text('77 bpm'), findsNothing);
        await tester.tap(find.text('Einstellungen').last);
        await tester.pumpAndSettle();
        expect(find.text('Anmelden'), findsOneWidget);
        http.json({'token': 'test-only-token', 'user': testUser});
        http.json({'records': []});
        await account.login('rider@example.invalid', 'test-only-password');
        await tester.tap(find.text('Workouts').last);
        await tester.pumpAndSettle();
        expect(
          find.text('Keine Workouts in deiner Bibliothek.'),
          findsOneWidget,
        );
        await tester.tap(find.text('Heute').last);
        await tester.pumpAndSettle();
        expect(find.text('Keine kommenden Einheiten geplant.'), findsOneWidget);
        expect(find.text('Kein Profil vorhanden.'), findsOneWidget);
        await tester.pumpWidget(const SizedBox());
        await tester.pump();
      },
    );
  }
}
