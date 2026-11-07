import 'dart:convert';
import 'dart:io';

class ApiFailure implements Exception {
  const ApiFailure(this.message);
  final String message;
  @override
  String toString() => message;
}

class StudioApi {
  StudioApi(String endpoint) : origin = Uri.tryParse(endpoint);
  final Uri? origin;
  final HttpClient _client = HttpClient()
    ..connectionTimeout = const Duration(seconds: 6);
  Cookie? _session;

  bool get configured {
    final url = origin;
    return url != null &&
        url.scheme == 'https' &&
        url.host.isNotEmpty &&
        url.userInfo.isEmpty &&
        (url.path.isEmpty || url.path == '/') &&
        !url.hasQuery &&
        !url.hasFragment;
  }

  Future<Map<String, dynamic>> request(
    String path, [
    Map<String, String>? body,
  ]) async {
    if (!configured) throw const ApiFailure('يلزم إعداد عنوان الخادم HTTPS.');
    final url = origin!.replace(path: '/api/$path');
    final request = await (body == null
        ? _client.getUrl(url)
        : _client.postUrl(url));
    request.followRedirects = false;
    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    if (_session case final session?) request.cookies.add(session);
    if (body != null) {
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(body));
    }
    final response = await request.close().timeout(const Duration(seconds: 8));
    final raw = await utf8.decoder
        .bind(response)
        .join()
        .timeout(const Duration(seconds: 8));
    final result = jsonDecode(raw) as Map<String, dynamic>;
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiFailure(result['error'] as String? ?? 'تعذّر إكمال الطلب.');
    }
    for (final cookie in response.cookies) {
      if (cookie.name == '__Host-session' && cookie.secure && cookie.httpOnly) {
        _session = cookie.maxAge == 0 ? null : cookie;
      }
    }
    return result;
  }

  void close() => _client.close(force: true);
}
