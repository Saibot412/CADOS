import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../account/account_controller.dart';
import '../account/api.dart';
import '../catalog/records.dart';

class WorkoutImportSource {
  const WorkoutImportSource(this.filename, this.content);
  final String filename;
  final String content;
}

class WorkoutImportController extends ChangeNotifier {
  WorkoutImportController(this.account)
    : sourceGeneration = account.syncGeneration;

  final AccountController account;
  int sourceGeneration;
  bool busy = false;
  String? error;
  WorkoutRecord? imported;
  bool _disposed = false;

  Future<bool> import(String filename, String content) async {
    if (busy) return false;
    imported = null;
    error = null;
    final safeName = filename.replaceAll('\\', '/').split('/').last.trim();
    final suffix = safeName.toLowerCase().endsWith('.json')
        ? '.json'
        : safeName.toLowerCase().endsWith('.zwo')
        ? '.zwo'
        : null;
    if (safeName.isEmpty || suffix == null) {
      error = 'Bitte eine JSON- oder ZWO-Datei auswählen.';
      _changed();
      return false;
    }
    final byteLength = utf8.encode(content).length;
    if (byteLength == 0 || byteLength > 2000000) {
      error = 'Die Importdatei muss zwischen 1 Byte und 2 MB groß sein.';
      _changed();
      return false;
    }

    busy = true;
    _changed();
    try {
      imported = await account.importWorkout(
        filename: safeName,
        content: content,
        contentType: suffix == '.json'
            ? 'application/json; charset=utf-8'
            : 'application/xml; charset=utf-8',
        expectedGeneration: sourceGeneration,
      );
      sourceGeneration = account.syncGeneration;
      return true;
    } catch (caught) {
      error = caught is ApiFailure && caught.status == 409
          ? 'Die Workoutbibliothek wurde inzwischen geändert (409). Bitte neu laden.'
          : caught is ApiFailure
          ? caught.message
          : 'Die Datei konnte nicht sicher importiert werden.';
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
