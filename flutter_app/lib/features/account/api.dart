import 'dart:convert';

class ApiConfig {
  ApiConfig(String value) : base = _validate(value);
  static const defaultUrl = 'https://cados.saibot.at';
  final Uri base;
  static Uri _validate(String value) {
    final uri = Uri.tryParse(value.trim());
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path != '/')) {
      throw const FormatException(
        'HTTPS-Serveradresse ohne Pfad, Zugangsdaten oder Suchparameter eingeben.',
      );
    }
    return uri.replace(path: '');
  }

  Uri endpoint(String path) => base.resolve('/api/v1$path');
}

abstract interface class TokenStore {
  Future<String?> read(String server);
  Future<void> write(String server, String token);
  Future<void> delete(String server);
}

abstract interface class ConfigStore {
  Future<String?> read();
  Future<void> write(String value);
}

class HttpReply {
  const HttpReply(this.status, this.body);
  final int status;
  final String body;
}

abstract interface class ApiTransport {
  Future<HttpReply> send(
    String method,
    Uri uri,
    Map<String, String> headers,
    String? body,
  );

  Future<HttpReply> sendBytes(
    String method,
    Uri uri,
    Map<String, String> headers,
    List<int> body,
  );
}

class ApiFailure implements Exception {
  const ApiFailure(this.message, {this.status});
  final String message;
  final int? status;
  @override
  String toString() => message;
}

class CadosApi {
  CadosApi(this.transport, this.config);
  final ApiTransport transport;
  final ApiConfig config;
  Future<Map<String, dynamic>> uploadBytes(
    String path, {
    required String token,
    required List<int> content,
    required String contentType,
    required Map<String, String> query,
  }) async {
    HttpReply reply;
    try {
      reply = await transport
          .sendBytes(
            'POST',
            config.endpoint(path).replace(queryParameters: query),
            {
              'Content-Type': contentType,
              'X-Cados-Request': '1',
              'Authorization': 'Bearer $token',
            },
            content,
          )
          .timeout(const Duration(seconds: 20));
    } catch (_) {
      throw const ApiFailure(
        'Server nicht erreichbar. Verbindung prüfen und erneut versuchen.',
      );
    }
    if (reply.status < 200 || reply.status >= 300) {
      throw ApiFailure(
        reply.status == 401
            ? 'Anmeldung abgelaufen.'
            : 'Import fehlgeschlagen (${reply.status}).',
        status: reply.status,
      );
    }
    try {
      return jsonDecode(reply.body) as Map<String, dynamic>;
    } catch (_) {
      throw const ApiFailure('Ungültige Serverantwort.');
    }
  }

  Future<Map<String, dynamic>> request(
    String path, {
    String? token,
    Map<String, dynamic>? body,
  }) async {
    HttpReply reply;
    try {
      reply = await transport
          .send(body == null ? 'GET' : 'POST', config.endpoint(path), {
            'Content-Type': 'application/json',
            'X-Cados-Request': '1',
            if (token != null) 'Authorization': 'Bearer $token',
          }, body == null ? null : jsonEncode(body))
          .timeout(const Duration(seconds: 20));
    } catch (_) {
      throw const ApiFailure(
        'Server nicht erreichbar. Verbindung prüfen und erneut versuchen.',
      );
    }
    if (reply.status < 200 || reply.status >= 300) {
      throw ApiFailure(
        reply.status == 401
            ? 'Anmeldung abgelaufen oder E-Mail/Passwort falsch.'
            : 'Serveranfrage fehlgeschlagen (${reply.status}).',
        status: reply.status,
      );
    }
    try {
      return jsonDecode(reply.body) as Map<String, dynamic>;
    } catch (_) {
      throw const ApiFailure('Ungültige Serverantwort.');
    }
  }
}

class AccountUser {
  factory AccountUser.fromJson(Map<String, dynamic> json) {
    try {
      final user = AccountUser._parse(json);
      if (user.id.isEmpty || user.email.isEmpty) throw const FormatException();
      return user;
    } catch (_) {
      throw const FormatException('Ungültiges Konto vom Server.');
    }
  }
  AccountUser._parse(Map<String, dynamic> json)
    : id = json['id'] as String,
      email = json['email'] as String,
      admin = json['admin'] as bool,
      active = json['active'] as bool,
      raw = Map.unmodifiable(json);
  final String id, email;
  final bool admin, active;
  final Map<String, dynamic> raw;
}
