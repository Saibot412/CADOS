import 'package:cados_app/features/session/session_analysis.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> ftpPayload({int watts = 440}) => {
  'workout_name': 'FTP Ramp Test (ERG)',
  'ftp_watts': 300,
  'workout_payload': {
    'blocks': [
      {
        'type': 'steady',
        'label': 'Warmup',
        'duration_sec': 60,
        'target_watts': 100,
      },
      {
        'type': 'steady',
        'label': 'Step 1',
        'duration_sec': 120,
        'target_watts': 600,
      },
    ],
  },
  'samples': [
    for (var i = 0; i < 120; i++)
      {
        'duration_sec': 1,
        'elapsed_sec': i + 1,
        'workout_elapsed_sec': i,
        'watts': i >= 60 ? watts : 900,
        'heart_rate': 190,
        'segment': 0,
      },
  ],
};

void main() {
  test('FTP ramp uses measured step power, not targets or warmup', () {
    expect(ftpTestResult(ftpPayload()), {
      'old_ftp': 300,
      'method': '75_percent_best_continuous_minute',
      'eligible': true,
      'best_minute_watts': 440,
      'estimated_ftp': 330,
    });
    expect(ftpTestResult(ftpPayload(watts: 360))!['estimated_ftp'], 270);
    expect(
      ftpTestResult({...ftpPayload(), 'workout_name': 'FTP 20 minute test'}),
      isNull,
    );
  });

  test('partial minutes and pauses are not eligible', () {
    final partial = ftpPayload();
    partial['samples'] = (partial['samples'] as List).sublist(0, 90);
    expect(ftpTestResult(partial)!['eligible'], false);

    final split = ftpPayload();
    final samples = split['samples'] as List;
    for (final sample in samples.skip(90)) {
      (sample as Map<String, dynamic>)['segment'] = 1;
    }
    expect(ftpTestResult(split)!['eligible'], false);
  });
}
