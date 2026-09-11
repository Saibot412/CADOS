import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'features/heart_rate/heart_rate_controller.dart';
import 'features/trainer/ftms_spike_controller.dart';
import 'infrastructure/ble/scan_coordinator.dart';
import 'infrastructure/ble/universal_ble_heart_rate_transport.dart';
import 'infrastructure/ble/universal_ble_trainer_transport.dart';
import 'infrastructure/logging/file_diagnostic_logger.dart';
import 'infrastructure/logging/log_export.dart';
import 'infrastructure/preferences/file_device_preferences.dart';
import 'presentation/ftms_spike_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final directory = await getApplicationSupportDirectory();
  final logger = FileDiagnosticLogger(
    File('${directory.path}/diagnostics/cados.log'),
  );
  logger.log('CADOS migration alpha started');
  final preferences = FileDevicePreferences(
    Directory('${directory.path}/devices'),
  );
  final scanner = ScanCoordinator();
  final trainer = FtmsSpikeController(
    UniversalBleTrainerTransport(scanner),
    logger: logger,
    preferences: preferences,
  );
  final hr = HeartRateController(
    UniversalBleHeartRateTransport(scanner),
    logger,
    preferences,
  );
  await trainer.restore();
  await hr.restore();
  runApp(
    CadosFtmsSpike(
      controller: trainer,
      heartRate: hr,
      exportLog: supportsLogExport ? () => exportDiagnosticLog(logger) : null,
    ),
  );
}
