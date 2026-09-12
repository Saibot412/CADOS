import 'package:cados_app/presentation/account_settings.dart';
import 'package:cados_app/presentation/profile_editor.dart';
import 'package:cados_app/presentation/zones_panel.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'record_mutation_test.dart' show profile, signedIn;

void main() {
  for (final size in [const Size(430, 900), const Size(1200, 900)]) {
    testWidgets('profile and zones render responsively at $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final (account, _) = await signedIn();

      await tester.pumpWidget(
        MaterialApp(
          home: ProfileEditorPage(
            account: account,
            profile: account.catalog!.profiles.single,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Profil und Zonen'), findsOneWidget);
      expect(find.text('Leistungszonen'), findsOneWidget);
      expect(find.text('Herzfrequenzzonen'), findsOneWidget);
      expect(find.text('Z2 Endurance'), findsOneWidget);
      expect(find.text('H4 Schwelle'), findsOneWidget);
      expect(find.text('139-188 W'), findsOneWidget);
      expect(find.text('153-171 bpm'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('missing max HR is explicit instead of fabricated', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ZonesPanel(ftpWatts: 250))),
    );
    expect(find.text('Z1 Recovery'), findsOneWidget);
    expect(find.textContaining('Maximalpuls fehlt'), findsOneWidget);
    expect(find.textContaining('HFmax 190'), findsNothing);
  });

  testWidgets('invalid profile input stays local and visible', (tester) async {
    final (account, http) = await signedIn();
    await tester.pumpWidget(
      MaterialApp(
        home: ProfileEditorPage(
          account: account,
          profile: account.catalog!.profiles.single,
        ),
      ),
    );
    final requestCount = http.requests.length;
    await tester.enterText(find.byKey(const Key('profileFtp')), '29');
    await tester.tap(find.byKey(const Key('saveProfile')));
    await tester.pump();

    expect(find.byKey(const Key('profileError')), findsOneWidget);
    expect(find.textContaining('30 und 2000'), findsOneWidget);
    expect(http.requests, hasLength(requestCount));
  });

  testWidgets('saving refreshes profile and zone boundaries', (tester) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final (account, http) = await signedIn();
    final saved = profile(revision: 4);
    (saved['payload'] as Map<String, dynamic>)
      ..['ftp'] = 280
      ..['max_hr'] = 195;
    http.json({
      'records': [saved],
    });
    http.json({
      'records': [saved],
    });
    await tester.pumpWidget(
      MaterialApp(
        home: ProfileEditorPage(
          account: account,
          profile: account.catalog!.profiles.single,
        ),
      ),
    );
    await tester.enterText(find.byKey(const Key('profileFtp')), '280');
    await tester.enterText(find.byKey(const Key('profileMaxHr')), '195');
    await tester.tap(find.byKey(const Key('saveProfile')));
    await tester.pumpAndSettle();

    expect(find.text('Profil wurde vom Server gespeichert.'), findsOneWidget);
    expect(find.text('FTP 280 W'), findsOneWidget);
    expect(find.text('HFmax 195 bpm'), findsOneWidget);
    expect(find.text('155-210 W'), findsOneWidget);
    expect(find.text('157-176 bpm'), findsOneWidget);
  });

  testWidgets('cancel discards form text without a server request', (
    tester,
  ) async {
    final (account, http) = await signedIn();
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => ProfileEditorPage(
                    account: account,
                    profile: account.catalog!.profiles.single,
                  ),
                ),
              ),
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('profileName')), 'Unsaved');
    final requestCount = http.requests.length;
    await tester.tap(find.text('Abbrechen'));
    await tester.pumpAndSettle();

    expect(find.text('Open'), findsOneWidget);
    expect(account.catalog!.profiles.single.name, 'Rider');
    expect(http.requests, hasLength(requestCount));
  });

  testWidgets('settings profile card opens the editor', (tester) async {
    final (account, _) = await signedIn();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AccountSettings(
            account: account,
            devices: const SizedBox(),
            support: const SizedBox(),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Rider'));
    await tester.pumpAndSettle();
    expect(find.text('Profil und Zonen'), findsOneWidget);
  });
}
