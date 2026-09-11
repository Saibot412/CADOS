import 'dart:io';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/infrastructure/session/file_session_journal.dart';
import 'package:cados_app/features/session/session_payload.dart';
import 'package:cados_app/features/session/workout_session_controller.dart';
import 'package:cados_app/features/workout/workout_engine.dart';

import 'session_helpers.dart';

SessionData journalData() => SessionData(
  id: sessionId,
  server: 'https://cados.saibot.at',
  accountId: 'account',
  workoutId: '065adcb9-77e1-46c3-809b-2c4d2ea50446',
  workoutPayload: workoutPayload(),
  profile: {
    'id': '395599cb-cc7b-409d-bfef-50d70e8adf8b',
    'name': 'Test rider',
    'ftp': 250,
  },
  ftp: 250,
  startedAt: '2026-09-11T00:00:00Z',
  planId: 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d',
);
void main() {
  late Directory dir;
  late File file;
  late FileSessionJournal journal;
  setUp(() async {
    dir = await Directory.systemTemp.createTemp('cados-journal-test-');
    file = File('${dir.path}/journal.json');
    journal = FileSessionJournal(file);
  });
  tearDown(() async {
    await dir.delete(recursive: true);
  });
  test('atomic draft and outbox survive restart; duplicate finalization is idempotent', () async {
    final data = journalData()..elapsed = 2;
    data.sample(
      duration: 2,
      from: 0,
      watts: 170,
      cadence: null,
      hr: null,
      target: 150,
      block: 0,
    );
    await journal.checkpoint(data.draft());
    final loaded = await FileSessionJournal(file).load();
    expect(loaded.draft!['elapsed_sec'], 2);
    expect(loaded.draft!['plan_id'], 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d');
    final entry = data.finalize('stopped', DateTime.utc(2026, 9, 11));
    await journal.finalize(entry);
    await journal.finalize(entry);
    final finalState = await FileSessionJournal(file).load();
    expect(finalState.draft, isNull);
    expect(finalState.outbox.length, 1);
    await journal.checkpoint(data.draft());
    expect((await journal.load()).draft, isNull);
    expect(await file.readAsString(), isNot(contains('token')));
    await journal.acknowledge(sessionId);
    expect((await journal.load()).outbox, isEmpty);
  });
  test('partial temporary write never replaces good state; corrupt committed state is retained', () async {
    await journal.checkpoint(journalData().draft());
    await File('${file.path}.tmp').writeAsString('{interrupted');
    expect((await FileSessionJournal(file).load()).draft, isNotNull);
    await file.writeAsString('{corrupt');
    await expectLater(journal.load(), throwsFormatException);
    await expectLater(
      journal.checkpoint(journalData().draft()),
      throwsFormatException,
    );
    expect(await file.readAsString(), '{corrupt');
  });
  test('bounded files and full outbox preserve draft rather than silently lose sessions', () async {
    await journal.checkpoint(journalData().draft());
    final original = await file.readAsString();
    await expectLater(
      FileSessionJournal(file, maxBytes: 8).load(),
      throwsFormatException,
    );
    expect(await file.readAsString(), original);
    final constrained = FileSessionJournal(file, maxEntries: 0);
    await expectLater(
      constrained.finalize(
        journalData().finalize('stopped', DateTime.utc(2026)),
      ),
      throwsFormatException,
    );
    expect((await journal.load()).draft, isNotNull);
    expect((await journal.load()).outbox, isEmpty);
    final oversized = journalData().draft();
    oversized['extra'] = 'x' * 5000;
    await expectLater(
      FileSessionJournal(file, maxBytes: 2000).checkpoint(oversized),
      throwsFormatException,
    );
    expect(await file.readAsString(), original);
  });
  test(
    'serialized checkpoint/finalization cannot resurrect a finalized draft',
    () async {
      final data = journalData();
      await Future.wait([
        journal.checkpoint(data.draft()),
        journal.finalize(data.finalize('stopped', DateTime.utc(2026))),
        journal.checkpoint(data.draft()),
      ]);
      expect((await journal.load()).draft, isNull);
      expect((await journal.load()).outbox.length, 1);
    },
  );
  test('recovery is paused, keeps identity/time/payload and never sends a command automatically', () async {
    final h = SessionHarness();
    await h.prepare();
    await h.session.start();
    await h.step();
    await h.step();
    await h.session.pause();
    final draft = h.journal.draft!;
    await journal.checkpoint(draft);
    final recovered = WorkoutSessionController(
      account: h.account,
      trainer: h.trainer,
      journal: FileSessionJournal(file),
      clock: h.clock,
      ticker: TestTicker(),
    );
    final starts = h.transport.starts;
    await recovered.initialize();
    expect(recovered.recovery, isNotNull);
    expect(h.transport.starts, starts);
    await recovered.recover();
    expect(recovered.state, WorkoutState.paused);
    expect(recovered.engine!.elapsed, 1);
    expect(recovered.data!.id, sessionId);
    expect(recovered.planId, 'ae2b4ea1-7d26-458e-b2c6-a8c7844ebf3d');
    expect(
      jsonEncode(recovered.data!.workoutPayload),
      jsonEncode(workoutPayload()),
    );
    await recovered.tick();
    expect(h.transport.starts, starts);
    await recovered.resume();
    expect(h.transport.starts, starts + 1);
    expect(recovered.state, WorkoutState.waitingForPedal);
    await recovered.shutdown();
    recovered.dispose();
    await h.close();
  });
}
