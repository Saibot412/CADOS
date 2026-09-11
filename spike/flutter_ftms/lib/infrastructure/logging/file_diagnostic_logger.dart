import 'dart:async';
import 'dart:convert';
import 'dart:io';

import '../../core/diagnostic_logger.dart';

class FileDiagnosticLogger implements DiagnosticLogger {
  FileDiagnosticLogger(
    this.file, {
    this.capacity = 250,
    this.maxBytes = 1024 * 1024,
    this.retainedFiles = 3,
  }) : assert(capacity > 0),
       assert(maxBytes > 0),
       assert(retainedFiles >= 0);
  final File file;
  final int capacity;
  final int maxBytes;
  final int retainedFiles;
  final List<String> _lines = [];
  final _changes = StreamController<void>.broadcast();
  Future<void> _pending = Future.value();
  Object? writeError;
  bool _closed = false;
  @override
  List<String> get lines => List.unmodifiable(_lines);
  @override
  Stream<void> get changes => _changes.stream;
  @override
  void log(String message) {
    if (_closed) return;
    final line = '${DateTime.now().toUtc().toIso8601String()} $message';
    _lines.insert(0, line);
    if (_lines.length > capacity) _lines.removeLast();
    _changes.add(null);
    _pending = _pending.then((_) async {
      try {
        await file.parent.create(recursive: true);
        var bytes = utf8.encode('$line\n');
        if (bytes.length > maxBytes) {
          bytes = utf8.encode(
            '${DateTime.now().toUtc().toIso8601String()} '
            '[diagnostic entry exceeded $maxBytes bytes]\n',
          );
        }
        if (await file.exists() &&
            await file.length() + bytes.length > maxBytes) {
          await _rotate();
        }
        await file.writeAsBytes(bytes, mode: FileMode.append, flush: true);
      } catch (e) {
        writeError = e;
      }
    });
  }

  Future<void> _rotate() async {
    if (retainedFiles == 0) {
      if (await file.exists()) await file.delete();
      return;
    }
    for (var generation = retainedFiles; generation >= 1; generation--) {
      final source = generation == 1
          ? file
          : File('${file.path}.${generation - 1}');
      final target = File('${file.path}.$generation');
      if (await target.exists()) await target.delete();
      if (await source.exists()) await source.rename(target.path);
    }
  }

  @override
  Future<void> flush() async {
    await _pending;
    if (writeError != null) {
      throw FileSystemException('Diagnostic write failed: $writeError');
    }
  }

  @override
  Future<void> close() async {
    _closed = true;
    await _pending;
    await _changes.close();
  }
}
