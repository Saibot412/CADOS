import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/diagnostic_logger.dart';

class DiagnosticsPanel extends StatelessWidget {
  const DiagnosticsPanel({
    super.key,
    this.logger,
    this.fallback = const [],
    this.exportLog,
  });
  final DiagnosticLogger? logger;
  final List<String> fallback;
  final Future<void> Function()? exportLog;
  @override
  Widget build(BuildContext context) => StreamBuilder<void>(
    stream: logger?.changes,
    builder: (context, _) {
      final lines = logger?.lines ?? fallback;
      Future<void> action(Future<void> Function() callback) async {
        try {
          await callback();
        } catch (e) {
          if (context.mounted) {
            ScaffoldMessenger.of(context)
                .showSnackBar(SnackBar(content: Text('Diagnose: $e')));
          }
        }
      }

      return Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Diagnoseprotokoll'),
              Wrap(
                spacing: 8,
                children: [
                  TextButton.icon(
                    onPressed: lines.isEmpty
                        ? null
                        : () => action(
                            () => Clipboard.setData(
                              ClipboardData(text: lines.reversed.join('\n')),
                            ),
                          ),
                    icon: const Icon(Icons.copy),
                    label: const Text('Kopieren'),
                  ),
                  if (exportLog != null)
                    TextButton.icon(
                      onPressed: () => action(exportLog!),
                      icon: const Icon(Icons.save_alt),
                      label: const Text('Datei speichern'),
                    ),
                ],
              ),
              SizedBox(
                height: 230,
                child: lines.isEmpty
                    ? const Center(child: Text('Noch keine Ereignisse'))
                    : ListView.builder(
                        itemCount: lines.length,
                        itemBuilder: (context, index) => SelectableText(
                          lines[index],
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 12,
                          ),
                        ),
                      ),
              ),
            ],
          ),
        ),
      );
    },
  );
}
