import 'package:flutter/material.dart';

import '../features/trainer/trainer_controller.dart';
import '../features/trainer/ftms_transport.dart';
import '../features/heart_rate/heart_rate_controller.dart';
import '../core/device.dart';
import 'heart_rate_panel.dart';

String connectionLabel(ConnectionPhase phase) => switch (phase) {
  ConnectionPhase.idle => 'Nicht verbunden',
  ConnectionPhase.scanning => 'Suche läuft',
  ConnectionPhase.connecting => 'Verbindung wird hergestellt',
  ConnectionPhase.connected => 'Verbunden',
  ConnectionPhase.reconnecting => 'Wiederverbindung läuft',
  ConnectionPhase.failed => 'Verbindung fehlgeschlagen',
};

class DeviceSettings extends StatelessWidget {
  const DeviceSettings({
    super.key,
    required this.trainer,
    this.heartRate,
    required this.locked,
  });
  final TrainerController trainer;
  final HeartRateController? heartRate;
  final bool locked;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: trainer,
    builder: (context, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Trainer · ${connectionLabel(trainer.connection.phase)}'),
        if (locked)
          const Text(
            'Gerätewechsel erst nach Beenden der Einheit. Wiederverbindung zum bisherigen Trainer bleibt möglich.',
          ),
        if (trainer.error != null) Text(trainer.error!),
        FilledButton(
          onPressed: locked || trainer.busy
              ? null
              : trainer.scanning
              ? trainer.stopScan
              : trainer.scan,
          child: Text(trainer.scanning ? 'Suche stoppen' : 'Trainer suchen'),
        ),
        if (trainer.devices.isEmpty) const Text('Noch kein Trainer gefunden.'),
        for (final d in trainer.devices)
          ListTile(
            title: Text(d.name),
            trailing: TextButton(
              onPressed: locked || trainer.busy
                  ? null
                  : () => trainer.connect(d),
              child: const Text('Verbinden'),
            ),
          ),
        if (trainer.preferred != null)
          TextButton(
            onPressed: trainer.busy || trainer.connected
                ? null
                : () => trainer.connect(
                    FtmsDevice(
                      id: trainer.preferred!.id,
                      name: trainer.preferred!.name,
                    ),
                  ),
            child: Text('Letzter Trainer: ${trainer.preferred!.name}'),
          ),
        TextButton(
          onPressed: trainer.disconnect,
          child: const Text('Trainer trennen / Wiederverbindung abbrechen'),
        ),
        if (heartRate != null) HeartRatePanel(controller: heartRate!),
      ],
    ),
  );
}
