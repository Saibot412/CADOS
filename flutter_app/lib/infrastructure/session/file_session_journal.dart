import 'dart:convert';
import 'dart:io';

import '../../features/session/session_ports.dart';
import '../../features/session/session_payload.dart';
import '../../features/session/session_contract.dart';

/// One atomic state transition covers draft -> outbox. Never delete a draft
/// before its finalized entry is durable. A failed write preserves the old file.
class FileSessionJournal implements SessionJournal {
  FileSessionJournal(
    this.file, {
    this.maxBytes = 64 * 1024 * 1024,
    this.maxEntries = 20,
  });
  final File file;
  final int maxBytes, maxEntries;
  Future<void> _tail = Future.value();
  Future<T> _serial<T>(Future<T> Function() action) {
    final result = _tail.then((_) => action());
    _tail = result.then<void>((_) {}, onError: (Object _, StackTrace _) {});
    return result;
  }

  Future<JournalState> _read() async {
    if (!await file.exists()) return const JournalState(null, []);
    if (await file.length() > maxBytes) {
      throw const FormatException(
        'Trainingsspeicher überschreitet die Größenbegrenzung.',
      );
    }
    try {
      final handle = await file.open();
      late List<int> bytes;
      try {
        bytes = await handle.read(maxBytes + 1);
      } finally {
        await handle.close();
      }
      if (bytes.length > maxBytes) throw const FormatException();
      final raw = jsonDecode(utf8.decode(bytes)) as Map<String, dynamic>;
      if (raw['version'] != 1) throw const FormatException();
      final draft = raw['draft'] as Map<String, dynamic>?;
      if (draft != null) SessionData.restore(draft);
      final outbox = (raw['outbox'] as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      if (outbox.length > maxEntries) throw const FormatException();
      final ids = <String>{};
      for (final entry in outbox) {
        validateSessionEntry(entry);
        final record = entry['record'] as Map<String, dynamic>;
        if (entry['server'] is! String ||
            entry['account_id'] is! String ||
            record['id'] is! String ||
            record['payload'] is! Map<String, dynamic> ||
            record['kind'] != 'session' ||
            record['revision'] != 0 ||
            record['shared'] != false ||
            record['deleted'] != false ||
            !ids.add(record['id'] as String)) {
          throw const FormatException();
        }
      }
      return JournalState(draft, outbox);
    } catch (_) {
      throw const FormatException(
        'Trainingsspeicher beschädigt. Datei bleibt unverändert; bitte Support kontaktieren.',
      );
    }
  }

  Future<void> _write(
    Map<String, dynamic>? draft,
    List<Map<String, dynamic>> outbox,
  ) async {
    final bytes = utf8.encode(
      jsonEncode({'version': 1, 'draft': draft, 'outbox': outbox}),
    );
    if (bytes.length > maxBytes || outbox.length > maxEntries) {
      throw const FormatException(
        'Trainingsspeicher voll. Bitte ausstehende Einheiten synchronisieren.',
      );
    }
    await file.parent.create(recursive: true);
    final temp = File('${file.path}.tmp');
    await temp.writeAsBytes(bytes, flush: true);
    await temp.rename(file.path);
  }

  @override
  Future<JournalState> load() => _serial(_read);
  @override
  Future<void> checkpoint(Map<String, dynamic> draft) {
    final snapshot = copyJson(draft);
    return _serial(() async {
      final state = await _read();
      if (state.outbox.any(
        (e) => (e['record'] as Map)['id'] == snapshot['session_id'],
      )) {
        return;
      }
      await _write(snapshot, state.outbox);
    });
  }

  @override
  Future<void> discard() => _serial(() async {
    final state = await _read();
    await _write(null, state.outbox);
  });
  @override
  Future<void> finalize(Map<String, dynamic> entry) {
    final snapshot = copyJson(entry);
    validateSessionEntry(snapshot);
    return _serial(() async {
      final state = await _read();
      final id = (snapshot['record'] as Map)['id'];
      final entries = [...state.outbox];
      final existing = entries.where((e) => (e['record'] as Map)['id'] == id);
      if (existing.isEmpty) {
        entries.add(snapshot);
      } else if (jsonEncode(existing.single) != jsonEncode(snapshot)) {
        throw const FormatException(
          'Session-ID bereits mit anderem Inhalt gespeichert.',
        );
      }
      await _write(
        state.draft?['session_id'] == id ? null : state.draft,
        entries,
      );
    });
  }

  @override
  Future<void> acknowledge(String id) => _serial(() async {
    final state = await _read();
    await _write(
      state.draft,
      state.outbox.where((e) => (e['record'] as Map)['id'] != id).toList(),
    );
  });
}
