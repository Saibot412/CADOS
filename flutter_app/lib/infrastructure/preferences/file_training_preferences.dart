import 'dart:convert';
import 'dart:io';

import '../../features/session/training_preferences.dart';

class FileTrainingPreferences implements TrainingPreferences {
  FileTrainingPreferences(this.file);

  final File file;
  Future<void> _pending = Future.value();

  @override
  Future<bool> readAdaptiveErg() async {
    try {
      final raw = jsonDecode(await file.readAsString());
      if (raw is! Map<String, dynamic> || raw['adaptive_erg'] is! bool) {
        return false;
      }
      return raw['adaptive_erg'] as bool;
    } on FileSystemException {
      return false;
    } on FormatException {
      return false;
    }
  }

  @override
  Future<void> saveAdaptiveErg(bool enabled) {
    final operation = _pending.then((_) async {
      await file.parent.create(recursive: true);
      final temporary = File('${file.path}.tmp');
      await temporary.writeAsString(
        jsonEncode({'adaptive_erg': enabled}),
        flush: true,
      );
      await temporary.rename(file.path);
    });
    _pending = operation.catchError((_) {});
    return operation;
  }
}
