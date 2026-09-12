import 'package:flutter/foundation.dart';

import 'api.dart';
import '../catalog/records.dart';
import '../session/session_acknowledgement.dart';
import '../session/session_contract.dart';

class AccountController extends ChangeNotifier {
  AccountController(this.transport, this.tokens, this.settings);
  final ApiTransport transport;
  final TokenStore tokens;
  final ConfigStore settings;
  ApiConfig config = ApiConfig(ApiConfig.defaultUrl);
  AccountUser? user;
  Catalog? catalog;
  String? error, _token;
  int syncGeneration = 0;
  bool busy = false;
  bool _disposed = false;
  CadosApi get _api => CadosApi(transport, config);
  void _changed() {
    if (!_disposed) notifyListeners();
  }

  Future<void> _run(
    Future<void> Function() action, {
    bool propagate = false,
  }) async {
    if (busy) {
      if (propagate) throw const ApiFailure('Konto ist noch beschäftigt.');
      return;
    }
    busy = true;
    error = null;
    _changed();
    try {
      await action();
    } catch (e) {
      error = e is ApiFailure
          ? e.message
          : e is FormatException
          ? 'Ungültige Konfiguration oder Serverantwort.'
          : 'Kontodaten oder sicherer Speicher nicht verfügbar. Bitte erneut versuchen.';
      if (e is ApiFailure && e.status == 401) {
        user = null;
        catalog = null;
        _token = null;
        try {
          await tokens.delete(config.base.toString());
        } catch (_) {
          error = 'Anmeldung abgelaufen. Sicherer Speicher konnte nicht geleert werden.';
        }
      }
      if (propagate) rethrow;
    } finally {
      busy = false;
      _changed();
    }
  }

  Future<void> restore() => _run(() async {
    user = null;
    catalog = null;
    config = ApiConfig(await settings.read() ?? ApiConfig.defaultUrl);
    _token = await tokens.read(config.base.toString());
    if (_token == null) return;
    catalog = null;
    user = AccountUser.fromJson(await _api.request('/auth/me', token: _token));
    await _sync();
  });
  Future<void> login(String email, String password) => _run(() async {
    final reply = await _api.request(
      '/auth/login',
      body: {'email': email.trim(), 'password': password},
    );
    final token = reply['token'] as String;
    final authenticated = AccountUser.fromJson(
      reply['user'] as Map<String, dynamic>,
    );
    try {
      await tokens.write(config.base.toString(), token);
    } catch (_) {
      try {
        await _api.request('/auth/logout', token: token, body: {});
      } catch (_) {}
      rethrow;
    }
    _token = token;
    user = authenticated;
    catalog = null;
    await _sync();
  });
  Future<void> _sync() async {
    catalog = null;
    catalog = Catalog.fromJson(await _api.request('/sync', token: _token));
    syncGeneration++;
  }

  Future<void> refresh() => _run(() async {
    if (_token == null) return;
    catalog = null;
    user = AccountUser.fromJson(await _api.request('/auth/me', token: _token));
    await _sync();
  });
  Future<void> logout() => _run(() async {
    var revoked = true;
    try {
      if (_token != null) {
        await _api.request('/auth/logout', token: _token, body: {});
      }
    } catch (_) {
      revoked = false;
    }
    user = null;
    catalog = null;
    _token = null;
    await tokens.delete(config.base.toString());
    if (!revoked) error = 'Lokal abgemeldet. Server nicht erreichbar; Abmeldung am Server konnte nicht bestätigt werden.';
  });
  Future<void> changeServer(String value) => _run(() async {
    final next = ApiConfig(value);
    if (next.base == config.base) return;
    // Never send a token issued by one origin to another origin.
    await settings.write(next.base.toString());
    config = next;
    user = null;
    catalog = null;
    _token = null;
  });
  Future<void> adoptFtp(String sessionId, int profileRevision) =>
      _run(() async {
        if (_token == null || user == null || catalog == null) {
          throw const ApiFailure(
            'Für die FTP-Übernahme ist eine Anmeldung erforderlich.',
          );
        }
        await _api.request(
          '/sessions/$sessionId/ftp',
          token: _token,
          body: {'profile_revision': profileRevision},
        );
        user = AccountUser.fromJson(
          await _api.request('/auth/me', token: _token),
        );
        await _sync();
      }, propagate: true);

  Future<void> uploadSession(Map<String, dynamic> entry) => _run(() async {
    if (_token == null ||
        user == null ||
        entry['account_id'] != user!.id ||
        entry['server'] != config.base.toString()) {
      throw const ApiFailure(
        'Für dieses Training ist das ursprüngliche Konto erforderlich.',
      );
    }
    validateSessionEntry(entry);
    final change = entry['record'];
    if (change is! Map<String, dynamic> ||
        change['kind'] != 'session' ||
        change['revision'] != 0 ||
        change['shared'] != false ||
        change['deleted'] != false) {
      throw const FormatException('Ungültiger Session-Datensatz.');
    }
    // Validate locally and reconcile a response lost after a previous commit.
    Catalog.fromJson({
      'records': [change],
    });
    final snapshot = Catalog.fromJson(
      await _api.request('/sync', token: _token),
    );
    final existing = snapshot.records
        .where((r) => r.id == change['id'])
        .toList();
    if (existing.isNotEmpty) {
      if (existing.length != 1 ||
          !sessionAcknowledged(existing.single, change)) {
        throw const ApiFailure(
          'Session-Konflikt; lokale Einheit bleibt erhalten.',
          status: 409,
        );
      }
      catalog = snapshot;
      syncGeneration++;
      return;
    }
    final result = Catalog.fromJson(
      await _api.request(
        '/sync',
        token: _token,
        body: {
          'changes': [change],
        },
      ),
    );
    if (result.records.length != 1 ||
        !sessionAcknowledged(result.records.single, change)) {
      throw const ApiFailure(
        'Server hat die Session nicht eindeutig bestätigt.',
      );
    }
    await _sync(); // Includes server-side profile max-HR changes.
  }, propagate: true);

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
