import 'package:flutter/foundation.dart';

import '../account/account_controller.dart';
import '../account/api.dart';
import 'records.dart';

/// Serializes one revision-bound record draft against the catalog generation
/// from which it was opened.
class RecordMutationController extends ChangeNotifier {
  RecordMutationController(this.account)
    : sourceGeneration = account.syncGeneration;

  final AccountController account;
  int sourceGeneration;
  bool busy = false;
  bool saved = false;
  String? error;
  bool _disposed = false;

  Future<bool> create({
    required String id,
    required String kind,
    required Map<String, dynamic> payload,
    bool shared = false,
  }) => _mutate({
    'id': id,
    'kind': kind,
    'revision': 0,
    'deleted': false,
    'shared': shared,
    'payload': payload,
  });

  Future<bool> update(SyncRecord current, Map<String, dynamic> payload) =>
      _mutate({
        'id': current.id,
        'kind': current.kind,
        'revision': current.revision,
        'deleted': false,
        'shared': current.shared,
        'payload': payload,
      });

  Future<bool> delete(SyncRecord current) => _mutate({
    'id': current.id,
    'kind': current.kind,
    'revision': current.revision,
    'deleted': true,
    'shared': current.shared,
    'payload': current.payload,
  });

  Future<bool> _mutate(Map<String, dynamic> change) async {
    if (busy) return false;
    busy = true;
    saved = false;
    error = null;
    _changed();
    try {
      await account.mutateRecord(change, expectedGeneration: sourceGeneration);
      sourceGeneration = account.syncGeneration;
      saved = true;
      return true;
    } catch (caught) {
      error = caught is ApiFailure && caught.status == 409
          ? 'Die Daten wurden inzwischen geändert (409). Bitte neu laden und Änderungen prüfen.'
          : caught is ApiFailure
          ? caught.message
          : caught is FormatException
          ? 'Die Änderung enthält ungültige Daten.'
          : 'Die Änderung konnte nicht sicher gespeichert werden.';
      return false;
    } finally {
      busy = false;
      _changed();
    }
  }

  void _changed() {
    if (!_disposed) super.notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
