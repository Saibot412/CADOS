class SensorDevice {
  const SensorDevice(this.id, this.name);
  final String id;
  final String name;
}

enum ConnectionPhase {
  idle,
  scanning,
  connecting,
  connected,
  reconnecting,
  failed,
}

abstract interface class DevicePreferences {
  Future<SensorDevice?> read(String role);
  Future<void> save(String role, SensorDevice device);
}
