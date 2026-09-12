import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../features/account/api.dart';

class HttpApiTransport implements ApiTransport {
  HttpApiTransport(this.client);
  final http.Client client;
  @override
  Future<HttpReply> send(
    String method,
    Uri uri,
    Map<String, String> headers,
    String? body,
  ) async {
    final request = http.Request(method, uri)
      ..headers.addAll(headers)
      ..followRedirects = false;
    if (body != null) request.body = body;
    final response = await http.Response.fromStream(await client.send(request));
    return HttpReply(response.statusCode, response.body);
  }

  @override
  Future<HttpReply> sendBytes(
    String method,
    Uri uri,
    Map<String, String> headers,
    List<int> body,
  ) async {
    final request = http.Request(method, uri)
      ..headers.addAll(headers)
      ..followRedirects = false
      ..bodyBytes = List<int>.from(body);
    final response = await http.Response.fromStream(await client.send(request));
    return HttpReply(response.statusCode, response.body);
  }
}

class SecureTokenStore implements TokenStore {
  SecureTokenStore(this.storage);
  final FlutterSecureStorage storage;
  String _key(String server) => 'cados.session.${Uri.encodeComponent(server)}';
  @override
  Future<String?> read(String server) => storage.read(key: _key(server));
  @override
  Future<void> write(String server, String token) =>
      storage.write(key: _key(server), value: token);
  @override
  Future<void> delete(String server) => storage.delete(key: _key(server));
}

class FileConfigStore implements ConfigStore {
  FileConfigStore(this.file);
  final File file;
  @override
  Future<String?> read() async =>
      await file.exists() ? file.readAsString() : null;
  @override
  Future<void> write(String value) async {
    await file.parent.create(recursive: true);
    final temporary = File('${file.path}.tmp');
    await temporary.writeAsString(value, flush: true);
    await temporary.rename(file.path);
  }
}
