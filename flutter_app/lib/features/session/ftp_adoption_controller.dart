import 'package:flutter/foundation.dart';

import '../account/account_controller.dart';
import '../account/api.dart';
import '../catalog/records.dart';

/// Applies a server-assessed FTP suggestion only after the presentation layer
/// has obtained explicit rider confirmation.
class FtpAdoptionController extends ChangeNotifier {
  FtpAdoptionController(this.account);

  final AccountController account;
  bool busy = false;
  bool applied = false;
  String? error;
  bool _disposed = false;

  void _changed() {
    if (!_disposed) super.notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  Future<void> adopt(SessionRecord session) async {
    if (busy) return;
    final result = session.ftpTestResult;
    if (result == null || result['eligible'] != true) {
      error = 'Für diese Einheit liegt kein übernehmbarer FTP-Vorschlag vor.';
      _changed();
      return;
    }
    if (result['applied_at'] != null) {
      error = 'Dieser FTP-Vorschlag wurde bereits übernommen.';
      _changed();
      return;
    }
    final profiles = account.catalog?.profiles;
    if (profiles == null || profiles.length != 1) {
      error =
          'Für die FTP-Übernahme ist genau ein aktuelles Profil erforderlich.';
      _changed();
      return;
    }

    busy = true;
    applied = false;
    error = null;
    _changed();
    try {
      await account.adoptFtp(
        session.record.id,
        profiles.single.record.revision,
      );
      final refreshed = account.catalog?.sessions
          .where((value) => value.record.id == session.record.id)
          .toList();
      final refreshedResult = refreshed?.length == 1
          ? refreshed!.single.ftpTestResult
          : null;
      if (refreshedResult == null || refreshedResult['applied_at'] == null) {
        throw const ApiFailure(
          'FTP wurde nicht eindeutig vom Server bestätigt.',
        );
      }
      applied = true;
    } catch (caught) {
      error = caught is ApiFailure ? caught.message : 'FTP konnte nicht sicher übernommen werden. Bitte aktualisieren und erneut versuchen.';
    } finally {
      busy = false;
      _changed();
    }
  }
}
