import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:cados_app/core/device.dart';
import 'package:cados_app/features/heart_rate/heart_rate.dart';
import 'package:cados_app/features/heart_rate/heart_rate_controller.dart';
import 'package:cados_app/core/diagnostic_logger.dart';

import 'package:cados_app/presentation/heart_rate_panel.dart';

class FakeHr implements HeartRateTransport {
  final found = StreamController<SensorDevice>.broadcast();
  final data = StreamController<HeartRateMeasurement>.broadcast();
  final lost = StreamController<void>.broadcast();
  final messages = StreamController<String>.broadcast();
  int connects = 0;
  bool off = false, scanning = false;
  @override
  Stream<SensorDevice> get devices => found.stream;
  @override
  Stream<HeartRateMeasurement> get measurements => data.stream;
  @override
  Stream<void> get disconnections => lost.stream;
  @override
  Stream<String> get logs => messages.stream;
  @override
  Future<void> scan() async {
    if (off) throw StateError('Bluetooth off');
    scanning = true;
  }

  @override
  Future<void> stopScan() async {
    scanning = false;
  }

  @override
  Future<void> connect(SensorDevice d) async {
    connects++;
    if (off) throw StateError('off');
  }

  @override
  Future<void> disconnect() async {}
  @override
  Future<void> dispose() async {
    await found.close();
    await data.close();
    await lost.close();
    await messages.close();
  }
}

class MemoryLog implements DiagnosticLogger {
  @override
  final List<String> lines = [];
  @override
  Stream<void> get changes => const Stream.empty();
  @override
  void log(String s) {
    lines.add(s);
  }

  @override
  Future<void> flush() async {}
  @override
  Future<void> close() async {}
}

class MemoryPreferences implements DevicePreferences {
  final values = <String, SensorDevice>{};
  @override
  Future<SensorDevice?> read(String role) async => values[role];
  @override
  Future<void> save(String role, SensorDevice d) async {
    values[role] = d;
  }
}

void main() {
  test(
    'HR diagnostics logs first and every 25th measurement, resets after loss',
    () async {
      final transport = FakeHr();
      final logger = MemoryLog();
      final c = HeartRateController(transport, logger, MemoryPreferences());
      await c.connect(const SensorDevice('h', 'Garmin'));
      for (var i = 0; i < 51; i++) {
        transport.data.add(const HeartRateMeasurement(143));
      }
      await Future<void>.delayed(Duration.zero);
      expect(
        logger.lines.where((s) => s.startsWith('HR measurement')).toList(),
        [
          'HR measurement #1: 143 bpm',
          'HR measurement #25: 143 bpm',
          'HR measurement #50: 143 bpm',
        ],
      );
      await c.disconnect();
      await c.connect(const SensorDevice('h', 'Garmin'));
      transport.data.add(const HeartRateMeasurement(144));
      await Future<void>.delayed(Duration.zero);
      expect(logger.lines.last, 'HR measurement #1: 144 bpm');
      c.dispose();
      await c.closed;
    },
  );

  testWidgets(
    'HR selection, telemetry, loss, reconnect, cancellation and preference restore',
    (tester) async {
      final logger = MemoryLog();
      final preferences = MemoryPreferences();
      final transport = FakeHr();
      final c = HeartRateController(transport, logger, preferences);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: HeartRatePanel(controller: c)),
        ),
      );
      transport.found.add(const SensorDevice('h', 'Chest strap'));
      await tester.pump();
      await c.connect(const SensorDevice('h', 'Chest strap'));
      await tester.pump();
      expect(c.connection.phase, ConnectionPhase.connected);
      transport.data.add(const HeartRateMeasurement(143));
      await tester.pumpAndSettle();
      expect(find.text('143 BPM'), findsOneWidget);
      transport.lost.add(null);
      await tester.pump();
      expect(c.measurement, isNull);
      expect(c.connection.phase, ConnectionPhase.reconnecting);
      await tester.pump(const Duration(seconds: 1));
      expect(transport.connects, 2);
      transport.lost.add(null);
      await tester.pump();
      await c.disconnect();
      await tester.pump(const Duration(seconds: 32));
      expect(transport.connects, 2);
      await c.restore();
      expect(c.preferred!.name, 'Chest strap');
      transport.off = true;
      await c.scan();
      expect(c.error, contains('Bluetooth off'));
      expect(c.scanning, false);
      await tester.pumpWidget(const SizedBox());
      c.dispose();
      await tester.pump();
      await tester.runAsync(() async {
        await logger.close();
      });
    },
  );
}
