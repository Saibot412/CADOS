import 'package:flutter/foundation.dart';

import '../account/account_controller.dart';
import '../catalog/record_mutation_controller.dart';
import '../catalog/records.dart';

class ProfileEditorController extends ChangeNotifier {
  ProfileEditorController(this.account, this.profile) {
    mutation.addListener(_relayMutation);
  }

  final AccountController account;
  late final RecordMutationController mutation = RecordMutationController(
    account,
  );
  ProfileRecord profile;
  String? error;
  bool _disposed = false;

  bool get busy => mutation.busy;
  bool get saved => mutation.saved;

  Future<bool> save({
    required String name,
    required String ftp,
    required String weightKg,
    required String maxHeartRate,
  }) async {
    final parsed = _validate(
      name: name,
      ftp: ftp,
      weightKg: weightKg,
      maxHeartRate: maxHeartRate,
    );
    if (parsed == null) {
      _changed();
      return false;
    }
    error = null;
    _changed();
    final payload = <String, dynamic>{
      ...profile.record.payload,
      'id': profile.record.id,
      'name': parsed.name,
      'ftp': parsed.ftp,
      'weight_kg': parsed.weightKg,
      'max_hr': parsed.maxHeartRate,
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    };
    final success = await mutation.update(profile.record, payload);
    if (!success) {
      error = mutation.error;
      _changed();
      return false;
    }
    final matches = account.catalog!.profiles
        .where((value) => value.record.id == profile.record.id)
        .toList();
    if (matches.length != 1) {
      error = 'Das aktualisierte Profil fehlt im Serverstand.';
      _changed();
      return false;
    }
    profile = matches.single;
    _changed();
    return true;
  }

  _ValidatedProfile? _validate({
    required String name,
    required String ftp,
    required String weightKg,
    required String maxHeartRate,
  }) {
    final cleanName = name.trim();
    if (cleanName.isEmpty || cleanName.length > 200) {
      error = 'Name muss zwischen 1 und 200 Zeichen lang sein.';
      return null;
    }
    final parsedFtp = int.tryParse(ftp.trim());
    if (parsedFtp == null || parsedFtp < 30 || parsedFtp > 2000) {
      error = 'FTP muss eine ganze Zahl zwischen 30 und 2000 W sein.';
      return null;
    }
    final cleanWeight = weightKg.trim().replaceAll(',', '.');
    final parsedWeight = cleanWeight.isEmpty
        ? null
        : double.tryParse(cleanWeight);
    if (cleanWeight.isNotEmpty &&
        (parsedWeight == null ||
            !parsedWeight.isFinite ||
            parsedWeight < 10 ||
            parsedWeight > 500)) {
      error = 'Gewicht muss zwischen 10 und 500 kg liegen oder leer bleiben.';
      return null;
    }
    final cleanMaxHr = maxHeartRate.trim();
    final parsedMaxHr = cleanMaxHr.isEmpty ? null : int.tryParse(cleanMaxHr);
    if (cleanMaxHr.isNotEmpty &&
        (parsedMaxHr == null || parsedMaxHr < 50 || parsedMaxHr > 250)) {
      error = 'Maximalpuls muss eine ganze Zahl zwischen 50 und 250 bpm sein oder leer bleiben.';
      return null;
    }
    return _ValidatedProfile(cleanName, parsedFtp, parsedWeight, parsedMaxHr);
  }

  void _relayMutation() => _changed();

  void _changed() {
    if (!_disposed) super.notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    mutation.removeListener(_relayMutation);
    mutation.dispose();
    super.dispose();
  }
}

class _ValidatedProfile {
  const _ValidatedProfile(
    this.name,
    this.ftp,
    this.weightKg,
    this.maxHeartRate,
  );
  final String name;
  final int ftp;
  final double? weightKg;
  final int? maxHeartRate;
}
