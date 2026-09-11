import 'package:flutter/material.dart';

import 'ftms/ftms_spike_controller.dart';
import 'ftms/universal_ble_trainer_transport.dart';
import 'ftms_spike_app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    CadosFtmsSpike(
      controller: FtmsSpikeController(UniversalBleTrainerTransport()),
    ),
  );
}
