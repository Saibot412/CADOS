import 'package:cados_app/features/session/training_metrics.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('metrics are independent of tick frequency', () {
    final regular = TrainingMetrics();
    final irregular = TrainingMetrics();
    for (final watts in [100, 300, 200]) {
      for (var i = 0; i < 240; i++) {
        regular.add(.25, watts, 90, 140);
      }
      for (var i = 0; i < 60; i++) {
        irregular
          ..add(.1, watts, 90, 140)
          ..add(.9, watts, 90, 140);
      }
    }
    expect(regular.summary(250), irregular.summary(250));
    expect(regular.summary(250)['avg_watts'], 200);
    expect(regular.summary(250)['max_watts'], 300);
    expect(regular.summary(250)['best_minute_watts'], 300);
  });

  test('one hour at FTP has hand-checkable NP, IF, TSS and work', () {
    final metrics = TrainingMetrics()..add(3600, 250, 90, 150);
    expect(metrics.summary(250), {
      'max_watts': 250,
      'avg_watts': 250,
      'max_cadence': 90,
      'avg_cadence': 90,
      'max_heart_rate': 150,
      'avg_heart_rate': 150,
      'best_minute_watts': 250,
      'work_kj': 900,
      'normalized_power': 250,
      'intensity_factor': 1.0,
      'tss': 100.0,
      'calories': 900,
    });
  });

  test('missing cadence and HR are excluded and power windows break', () {
    final metrics = TrainingMetrics()
      ..add(30, 400, null, null)
      ..breakPowerWindow()
      ..add(30, 400, 80, 150);
    final summary = metrics.summary(250);
    expect(summary['avg_cadence'], 80);
    expect(summary['avg_heart_rate'], 150);
    expect(summary['best_minute_watts'], 0);
  });
}
