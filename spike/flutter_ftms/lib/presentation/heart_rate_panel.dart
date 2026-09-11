import 'package:flutter/material.dart';

import '../features/heart_rate/heart_rate_controller.dart';

class HeartRatePanel extends StatelessWidget {
  const HeartRatePanel({super.key, required this.controller});
  final HeartRateController controller;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Herzfrequenz · ${controller.connection.phase.name}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text('${controller.measurement?.bpm ?? "–"} BPM'),
            if (controller.error != null || controller.connection.error != null)
              Text(controller.error ?? controller.connection.error!),
            FilledButton(
              onPressed: controller.scanning
                  ? controller.stopScan
                  : controller.scan,
              child: Text(
                controller.scanning ? 'HR Scan stoppen' : 'HR Sensor suchen',
              ),
            ),
            if (controller.preferred != null)
              TextButton(
                onPressed: () => controller.connect(controller.preferred!),
                child: Text('Letzter HR Sensor: ${controller.preferred!.name}'),
              ),
            ...controller.devices.map(
              (d) => ListTile(
                title: Text(d.name),
                trailing: TextButton(
                  onPressed: () => controller.connect(d),
                  child: const Text('HR verbinden'),
                ),
              ),
            ),
            TextButton(
              onPressed: controller.disconnect,
              child: const Text('HR trennen / Reconnect abbrechen'),
            ),
          ],
        ),
      ),
    ),
  );
}
