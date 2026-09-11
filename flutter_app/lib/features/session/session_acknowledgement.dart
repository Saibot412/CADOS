import 'package:collection/collection.dart';

import '../catalog/records.dart';

/// The server may derive ftp_test_result and metrics.max_heart_rate. Every other
/// submitted field must agree before an ambiguous earlier upload is acknowledged.
bool sessionAcknowledged(SyncRecord saved, Map<String, dynamic> submitted) {
  if (saved.id != submitted['id'] ||
      saved.kind != 'session' ||
      saved.shared ||
      saved.deleted ||
      saved.revision < 1) {
    return false;
  }
  final payload = submitted['payload'];
  if (payload is! Map<String, dynamic>) return false;
  const equal = DeepCollectionEquality();
  for (final key in payload.keys) {
    if (key == 'ftp_test_result') continue;
    if (key == 'metrics') {
      final metrics = payload[key];
      final actual = saved.payload[key];
      if (metrics is! Map || actual is! Map) return false;
      for (final field in metrics.keys) {
        if (field != 'max_heart_rate' &&
            !equal.equals(metrics[field], actual[field])) {
          return false;
        }
      }
    } else if (!equal.equals(saved.payload[key], payload[key])) {
      return false;
    }
  }
  return true;
}
