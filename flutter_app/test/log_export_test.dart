import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/infrastructure/logging/file_diagnostic_logger.dart';
import 'package:cados_app/infrastructure/logging/log_export.dart';

void main() {
  test(
    'export saves full flushed file, cancellation leaves it intact',
    () async {
      final dir = await Directory.systemTemp.createTemp('cados-export-');
      try {
        final logger = FileDiagnosticLogger(
          File('${dir.path}/source.log'),
          capacity: 1,
        );
        logger.log('first');
        logger.log('second');
        final destination = File('${dir.path}/saved.log');
        await exportDiagnosticLog(
          logger,
          choosePath: () async => destination.path,
        );
        expect(
          await destination.readAsString(),
          await logger.file.readAsString(),
        );
        expect(await destination.readAsLines(), hasLength(2));
        expect(logger.lines, hasLength(1));
        await exportDiagnosticLog(logger, choosePath: () async => null);
        expect(await destination.readAsLines(), hasLength(2));
        await logger.close();
      } finally {
        await dir.delete(recursive: true);
      }
    },
  );
}
