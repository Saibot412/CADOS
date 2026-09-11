import 'dart:convert';
import 'dart:io';

import '../../core/device.dart';

class FileDevicePreferences implements DevicePreferences {
  FileDevicePreferences(this.directory);
  final Directory directory;
  Future<void> _pending = Future.value();
  File _file(String role) {
    if (role != 'trainer' && role != 'heart_rate') throw ArgumentError(role);
    return File('${directory.path}/$role.json');
  }

  @override
  Future<SensorDevice?> read(String role) async {
    try {
      final value = jsonDecode(await _file(role).readAsString()) as Map;
      return SensorDevice(value['id'] as String, value['name'] as String);
    } on FileSystemException {
      return null;
    } on FormatException {
      return null;
    } on TypeError {
      return null;
    }
  }

  @override
  Future<void> save(String role, SensorDevice device) {
    final operation = _pending.then((_) => _save(role, device));
    _pending = operation.then<void>((_) {}, onError: (Object _) {});
    return operation;
  }

  Future<void> _save(String role, SensorDevice device) async {
    await directory.create(recursive: true);
    final file = _file(role);
    final temp = File('${file.path}.tmp');
    await temp.writeAsString(
      jsonEncode({'id': device.id, 'name': device.name}),
      flush: true,
    );
    await temp.rename(file.path);
  }
}
