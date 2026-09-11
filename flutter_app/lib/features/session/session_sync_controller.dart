import 'dart:async';

import 'package:flutter/foundation.dart';

import '../account/account_controller.dart';
import 'session_ports.dart';

class SessionSyncController extends ChangeNotifier {
  SessionSyncController({
    required this.account,
    required this.journal,
    required this.uploader,
  }) {
    account.addListener(_accountChanged);
  }
  final AccountController account;
  final SessionJournal journal;
  final SessionUploader uploader;
  int pending = 0;
  String? error;
  bool busy = false, loaded = false, _disposed = false;
  String? _generation;
  Future<void> closed = Future.value();
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _accountChanged() {
    final key =
        '${account.user?.id}:${account.config.base}:${account.syncGeneration}';
    if (!account.busy &&
        account.user != null &&
        account.catalog != null &&
        key != _generation) {
      _generation = key;
      if (!busy) unawaited(retry());
    }
  }

  Future<void> retry() {
    if (busy || _disposed) return closed;
    busy = true;
    error = null;
    _notify();
    closed = _retry();
    return closed;
  }

  Future<void> _retry() async {
    try {
      var stored = await journal.load();
      pending = stored.outbox.length;
      loaded = true;
      _notify();
      for (final entry in stored.outbox) {
        if (_disposed || account.user == null || account.busy) break;
        if (entry['account_id'] != account.user!.id ||
            entry['server'] != account.config.base.toString()) {
          continue;
        }
        await uploader.upload(entry);
        await journal.acknowledge((entry['record'] as Map)['id'] as String);
      }
      stored = await journal.load();
      pending = stored.outbox.length;
    } catch (_) {
      error = 'Einheit bleibt lokal gespeichert. Synchronisierung fehlgeschlagen; bitte erneut versuchen.';
    } finally {
      busy = false;
      _notify();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    account.removeListener(_accountChanged);
    super.dispose();
  }
}

class AccountSessionUploader implements SessionUploader {
  AccountSessionUploader(this.account);
  final AccountController account;
  @override
  Future<void> upload(Map<String, dynamic> entry) =>
      account.uploadSession(entry);
}
