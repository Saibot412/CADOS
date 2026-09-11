import 'dart:async';

import 'package:cados_ftms_spike/features/trainer/ftms_spike_controller.dart';
import 'package:cados_ftms_spike/features/trainer/ftms_transport.dart';
import 'package:flutter/material.dart';

import '../features/heart_rate/heart_rate_controller.dart';
import 'diagnostics_panel.dart';
import 'heart_rate_panel.dart';

class CadosFtmsSpike extends StatelessWidget {
  const CadosFtmsSpike({
    super.key,
    required this.controller,
    this.heartRate,
    this.exportLog,
  });

  final FtmsSpikeController controller;
  final HeartRateController? heartRate;
  final Future<void> Function()? exportLog;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'CADOS FTMS Test',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00A67D),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF081310),
        cardTheme: const CardThemeData(
          color: Color(0xFF11211C),
          margin: EdgeInsets.zero,
        ),
        useMaterial3: true,
      ),
      home: FtmsSpikeScreen(
        controller: controller,
        heartRate: heartRate,
        exportLog: exportLog,
      ),
    );
  }
}

class FtmsSpikeScreen extends StatefulWidget {
  const FtmsSpikeScreen({
    super.key,
    required this.controller,
    this.heartRate,
    this.exportLog,
  });
  final FtmsSpikeController controller;
  final HeartRateController? heartRate;
  final Future<void> Function()? exportLog;

  @override
  State<FtmsSpikeScreen> createState() => _FtmsSpikeScreenState();
}

class _FtmsSpikeScreenState extends State<FtmsSpikeScreen> {
  FtmsSpikeController get controller => widget.controller;

  @override
  void dispose() {
    widget.heartRate?.dispose();
    controller.dispose();
    unawaited(_closeResources());
    super.dispose();
  }

  Future<void> _closeResources() async {
    try {
      await Future.wait([
        controller.closed,
        if (widget.heartRate != null) widget.heartRate!.closed,
      ]);
    } catch (error) {
      debugPrint('CADOS controller shutdown failed: $error');
    } finally {
      try {
        await controller.logger?.close();
      } catch (error) {
        debugPrint('CADOS diagnostic logger shutdown failed: $error');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('CADOS · FTMS Trainer-Test'),
            backgroundColor: const Color(0xFF0C1915),
            actions: [
              _StatusBadge(state: controller.connectionState),
              const SizedBox(width: 16),
            ],
          ),
          body: SafeArea(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                _notice(),
                const SizedBox(height: 16),
                if (controller.error != null) _error(controller.error!),
                if (controller.error != null) const SizedBox(height: 16),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 850;
                    final left = _devicesPanel();
                    final right = _controlPanel();
                    if (!wide) {
                      return Column(
                        children: [left, const SizedBox(height: 16), right],
                      );
                    }
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(flex: 4, child: left),
                        const SizedBox(width: 16),
                        Expanded(flex: 6, child: right),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 16),
                if (widget.heartRate != null)
                  HeartRatePanel(controller: widget.heartRate!),
                const SizedBox(height: 16),
                DiagnosticsPanel(
                  logger: controller.logger,
                  fallback: controller.logs,
                  exportLog: widget.exportLog,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _notice() => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.science_outlined, color: Color(0xFFFFC857)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Technischer Spike – noch kein vollständiges CADOS. '
              'Nach Verbindungsabbruch werden Steuerfreigabe und Messdaten neu '
              'aufgebaut. Start und Zielleistung bleiben explizite Aktionen.',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ),
        ],
      ),
    ),
  );

  Widget _error(String text) => Material(
    color: Theme.of(context).colorScheme.errorContainer,
    borderRadius: BorderRadius.circular(12),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          const Icon(Icons.error_outline),
          const SizedBox(width: 10),
          Expanded(child: SelectableText(text)),
        ],
      ),
    ),
  );

  Widget _devicesPanel() => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '1 · Trainer finden',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            key: const Key('scanButton'),
            onPressed: controller.busy
                ? null
                : controller.scanning
                ? controller.stopScan
                : controller.scan,
            icon: controller.scanning
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.bluetooth_searching),
            label: Text(
              controller.scanning
                  ? 'FTMS-Scan läuft …'
                  : '8 Sekunden nach FTMS suchen',
            ),
          ),
          const SizedBox(height: 12),
          if (controller.devices.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Text(
                'Noch kein FTMS-Trainer gefunden. Trainer einschalten und '
                'andere Trainings-Apps vollständig schließen.',
                textAlign: TextAlign.center,
              ),
            )
          else
            ...controller.devices.map(_deviceTile),
          if (controller.preferred != null)
            TextButton(
              onPressed: controller.busy
                  ? null
                  : () => controller.connect(
                      FtmsDevice(
                        id: controller.preferred!.id,
                        name: controller.preferred!.name,
                      ),
                    ),
              child: Text('Letzter Trainer: ${controller.preferred!.name}'),
            ),
          Text('Verbindung: ${controller.connection.phase.name}'),
          if (controller.selectedDevice != null) ...[
            const Divider(height: 28),
            OutlinedButton.icon(
              onPressed: controller.disconnect,
              icon: const Icon(Icons.link_off),
              label: const Text('Trainer trennen / Reconnect abbrechen'),
            ),
          ],
        ],
      ),
    ),
  );

  Widget _deviceTile(FtmsDevice device) => ListTile(
    contentPadding: EdgeInsets.zero,
    leading: const CircleAvatar(child: Icon(Icons.directions_bike)),
    title: Text(device.name),
    subtitle: Text('${device.rssi ?? '–'} dBm · Bluetooth FTMS'),
    trailing: FilledButton.tonal(
      onPressed: controller.busy ? null : () => controller.connect(device),
      child: const Text('Verbinden'),
    ),
  );

  Widget _controlPanel() {
    final measurement = controller.measurement;
    final range = controller.powerRange;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '2 · Messen und steuern',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: _MetricCard(
                    label: 'Leistung',
                    value: measurement.powerWatts == null
                        ? '–'
                        : '${measurement.powerWatts} W',
                    icon: Icons.bolt,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _MetricCard(
                    label: 'Kadenz',
                    value: measurement.cadenceRpm == null
                        ? '–'
                        : '${measurement.cadenceRpm!.toStringAsFixed(1)} rpm',
                    icon: Icons.autorenew,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              range == null
                  ? 'Leistungsbereich: nicht gemeldet'
                  : 'Leistungsbereich: ${range.minimumWatts}–'
                        '${range.maximumWatts} W · ${range.incrementWatts}-W-Schritte',
            ),
            const Divider(height: 30),
            Text(
              'Zielleistung',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [100, 150, 200]
                  .map(
                    (watts) => FilledButton.tonalIcon(
                      key: Key('power$watts'),
                      onPressed: _controlsEnabled
                          ? () => controller.setPower(watts)
                          : null,
                      icon: const Icon(Icons.speed),
                      label: Text('$watts W'),
                    ),
                  )
                  .toList(),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                FilledButton.icon(
                  key: const Key('startButton'),
                  onPressed: _controlsEnabled ? controller.startTraining : null,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Start/Fortsetzen'),
                ),
                OutlinedButton.icon(
                  onPressed: _controlsEnabled ? controller.pauseTraining : null,
                  icon: const Icon(Icons.pause),
                  label: const Text('Pause'),
                ),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Theme.of(context).colorScheme.error,
                  ),
                  onPressed: _controlsEnabled ? controller.stopTraining : null,
                  icon: const Icon(Icons.stop),
                  label: const Text('Stop'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  bool get _controlsEnabled => controller.connected && !controller.busy;
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.state});
  final FtmsConnectionState state;

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (state) {
      FtmsConnectionState.connected => ('ERG bereit', const Color(0xFF55E6B5)),
      FtmsConnectionState.connecting => ('Verbinde …', const Color(0xFFFFC857)),
      FtmsConnectionState.disconnected => ('Nicht verbunden', Colors.white60),
    };
    return Center(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(30),
          border: Border.all(color: color.withValues(alpha: 0.5)),
        ),
        child: Text(label, style: TextStyle(color: color)),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.label,
    required this.value,
    required this.icon,
  });
  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0A1814),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          Icon(icon, color: const Color(0xFF55E6B5)),
          const SizedBox(height: 8),
          Text(value, style: Theme.of(context).textTheme.headlineSmall),
          Text(label, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}
