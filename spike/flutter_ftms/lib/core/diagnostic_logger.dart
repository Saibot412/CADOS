abstract interface class DiagnosticLogger {
  List<String> get lines;
  Stream<void> get changes;
  void log(String message);
  Future<void> flush();
  Future<void> close();
}
