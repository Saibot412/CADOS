import 'dart:io';

import 'package:file_selector/file_selector.dart';

import 'file_diagnostic_logger.dart';

Future<void> exportDiagnosticLog(
  FileDiagnosticLogger logger, {
  Future<String?> Function()? choosePath,
}) async {
  await logger.flush();
  final path = await (choosePath ?? _choosePath)();
  if (path == null) return;
  final destination = File(path);
  if (destination.absolute.path == logger.file.absolute.path) return;
  await destination.parent.create(recursive: true);
  await logger.file.openRead().pipe(destination.openWrite());
}

bool get supportsLogExport =>
    Platform.isLinux || Platform.isWindows || Platform.isMacOS;

Future<String?> _choosePath() async =>
    (await getSaveLocation(suggestedName: 'cados-diagnostics.log'))?.path;
