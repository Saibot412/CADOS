import '../../core/device.dart';

class HeartRateMeasurement {
  const HeartRateMeasurement(this.bpm);
  final int bpm;
  static HeartRateMeasurement parse(List<int> bytes) {
    if (bytes.isEmpty) throw const FormatException('Missing HR flags');
    final wide = bytes[0] & 1 != 0;
    if (bytes.length < (wide ? 3 : 2)) {
      throw const FormatException('Truncated HR measurement');
    }
    return HeartRateMeasurement(bytes[1] | (wide ? bytes[2] << 8 : 0));
  }
}

abstract interface class HeartRateTransport {
  Stream<SensorDevice> get devices;
  Stream<HeartRateMeasurement> get measurements;
  Stream<void> get disconnections;
  Stream<String> get logs;
  Future<void> scan();
  Future<void> stopScan();
  Future<void> connect(SensorDevice device);
  Future<void> disconnect();
  Future<void> dispose();
}
