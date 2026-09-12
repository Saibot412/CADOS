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

bool jsonValuesEqual(Object? left, Object? right) {
  if (left is Map<String, dynamic> && right is Map<String, dynamic>) {
    if (left.length != right.length || !left.keys.every(right.containsKey)) {
      return false;
    }
    return left.entries.every(
      (entry) => jsonValuesEqual(entry.value, right[entry.key]),
    );
  }
  if (left is List && right is List) {
    if (left.length != right.length) return false;
    for (var index = 0; index < left.length; index++) {
      if (!jsonValuesEqual(left[index], right[index])) return false;
    }
    return true;
  }
  return left == right;
}
