import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/core/device.dart';
import 'package:cados_app/infrastructure/logging/file_diagnostic_logger.dart';
import 'package:cados_app/infrastructure/preferences/file_device_preferences.dart';
import 'package:cados_app/infrastructure/preferences/file_training_preferences.dart';

void main() {
  late Directory dir;
  setUp(() async {
    dir = await Directory.systemTemp.createTemp('cados-test-');
  });
  tearDown(() async {
    await dir.delete(recursive: true);
  });
  test('bounded view rotates durable logs by size across instances', () async {
    final file = File('${dir.path}/logs/current.log');
    final logger = FileDiagnosticLogger(
      file,
      capacity: 2,
      maxBytes: 80,
      retainedFiles: 2,
    );
    for (var i = 0; i < 8; i++) {
      logger.log('entry-$i');
    }
    await logger.flush();
    expect(logger.lines.length, 2);
    expect(logger.lines.first, endsWith('entry-7'));
    for (final retained in [
      file,
      File('${file.path}.1'),
      File('${file.path}.2'),
    ]) {
      expect(await retained.length(), lessThanOrEqualTo(80));
    }
    expect(File('${file.path}.3').existsSync(), isFalse);
    await logger.close();
    final reopened = FileDiagnosticLogger(file, maxBytes: 80, retainedFiles: 2);
    reopened.log('entry-after-restart');
    await reopened.close();
    expect(await file.length(), lessThanOrEqualTo(80));
  });
  test('write failure is visible to export', () async {
    final logger = FileDiagnosticLogger(File(dir.path));
    logger.log('failure');
    await expectLater(logger.flush(), throwsA(isA<FileSystemException>()));
    await logger.close();
  });
  test('preferences persist independent trainer and HR choices and tolerate corrupt files', () async {
    final store = FileDevicePreferences(dir);
    expect(await store.read('trainer'), isNull);
    await store.save('trainer', const SensorDevice('t', 'KICKR'));
    await store.save('heart_rate', const SensorDevice('h', 'HR'));
    final reloaded = FileDevicePreferences(dir);
    expect((await reloaded.read('trainer'))!.name, 'KICKR');
    expect((await reloaded.read('heart_rate'))!.id, 'h');
    await File('${dir.path}/trainer.json').writeAsString('{');
    expect(await reloaded.read('trainer'), isNull);
  });
  test(
    'adaptive ERG preference persists safely and corrupt data defaults off',
    () async {
      final file = File('${dir.path}/training/preferences.json');
      final store = FileTrainingPreferences(file);
      expect(await store.readAdaptiveErg(), isFalse);
      await store.saveAdaptiveErg(true);
      expect(await FileTrainingPreferences(file).readAdaptiveErg(), isTrue);
      await store.saveAdaptiveErg(false);
      expect(await FileTrainingPreferences(file).readAdaptiveErg(), isFalse);
      await file.writeAsString('{');
      expect(await store.readAdaptiveErg(), isFalse);
    },
  );
}
