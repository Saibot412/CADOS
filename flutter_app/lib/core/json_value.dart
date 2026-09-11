/// Freeze nested JSON so UI consumers cannot mutate authoritative server records.
dynamic freezeJson(dynamic value) {
  if (value is Map<String, dynamic>) {
    return Map<String, dynamic>.unmodifiable(
      value.map((k, v) => MapEntry(k, freezeJson(v))),
    );
  }
  if (value is List) return List<dynamic>.unmodifiable(value.map(freezeJson));
  if (value == null ||
      value is String ||
      value is bool ||
      value is num && value.isFinite) {
    return value;
  }
  throw const FormatException('Ungültiger JSON-Wert.');
}
