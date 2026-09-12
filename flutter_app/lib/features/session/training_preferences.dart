abstract interface class TrainingPreferences {
  Future<bool> readAdaptiveErg();
  Future<void> saveAdaptiveErg(bool enabled);
}
