import 'dart:io';
import 'dart:async';

import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'features/account/account_controller.dart';
import 'infrastructure/account/production_stores.dart';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'features/heart_rate/heart_rate_controller.dart';
import 'features/trainer/trainer_controller.dart';
import 'infrastructure/ble/scan_coordinator.dart';
import 'infrastructure/ble/universal_ble_heart_rate_transport.dart';
import 'infrastructure/ble/universal_ble_trainer_transport.dart';
import 'infrastructure/logging/file_diagnostic_logger.dart';
import 'infrastructure/logging/log_export.dart';
import 'infrastructure/preferences/file_device_preferences.dart';
import 'infrastructure/preferences/file_training_preferences.dart';
import 'presentation/cados_app.dart';
import 'features/session/workout_session_controller.dart';
import 'features/session/session_sync_controller.dart';
import 'features/session/session_ports.dart';
import 'infrastructure/session/file_session_journal.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final directory = await getApplicationSupportDirectory();
  final logger = FileDiagnosticLogger(
    File('${directory.path}/diagnostics/cados.log'),
  );
  logger.log('CADOS started');
  final preferences = FileDevicePreferences(
    Directory('${directory.path}/devices'),
  );
  final scanner = ScanCoordinator();
  final trainer = TrainerController(
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
  final client = http.Client();
  final account = AccountController(
    HttpApiTransport(client),
    SecureTokenStore(const FlutterSecureStorage()),
    FileConfigStore(File('${directory.path}/server.txt')),
  );
  final clock = SystemSessionClock();
  final journal = FileSessionJournal(
    File('${directory.path}/training/journal.json'),
  );
  final trainingPreferences = FileTrainingPreferences(
    File('${directory.path}/training/preferences.json'),
  );
  final sync = SessionSyncController(
    account: account,
    journal: journal,
    uploader: AccountSessionUploader(account),
  );
  final session = WorkoutSessionController(
    account: account,
    trainer: trainer,
    heartRate: hr,
    journal: journal,
    clock: clock,
    ticker: PeriodicSessionTicker(),
    onFinalized: sync.retry,
    trainingPreferences: trainingPreferences,
  );
  await session.initialize();
  unawaited(sync.retry());
  unawaited(account.restore());
  runApp(
    CadosApp(
      account: account,
      session: session,
      sync: sync,
      closeHttp: client.close,
      controller: trainer,
      heartRate: hr,
      exportLog: supportsLogExport ? () => exportDiagnosticLog(logger) : null,
    ),
  );
}
