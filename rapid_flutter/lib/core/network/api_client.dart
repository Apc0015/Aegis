import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../errors/app_exception.dart';

const _storage = FlutterSecureStorage();
const _tokenKey = 'rapid_access_token';

/// Returns the stored JWT token (or null if not logged in).
Future<String?> getStoredToken() => _storage.read(key: _tokenKey);

/// Stores a new JWT token after login.
Future<void> storeToken(String token) => _storage.write(key: _tokenKey, value: token);

/// Clears the stored JWT token on logout.
Future<void> clearToken() => _storage.delete(key: _tokenKey);

/// Build a Dio instance for the RAPID API.
/// Pass [apiBase] (from --dart-define=API_BASE_URL=...) or defaults to localhost.
Dio buildDioClient({String? apiBase}) {
  const String defaultBase = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  final dio = Dio(
    BaseOptions(
      baseUrl: apiBase ?? defaultBase,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 120), // long for SSE + large docs
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    ),
  );

  // Auth interceptor — attach Bearer token to every request
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await getStoredToken();
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (DioException error, handler) {
        // Map Dio errors to typed AppExceptions
        final statusCode = error.response?.statusCode;
        final message = _extractMessage(error);

        if (statusCode == 401) {
          handler.reject(
            DioException(
              requestOptions: error.requestOptions,
              error: AuthException(message),
              type: error.type,
              response: error.response,
            ),
          );
        } else if (statusCode == 403) {
          handler.reject(
            DioException(
              requestOptions: error.requestOptions,
              error: ForbiddenException(message),
              type: error.type,
              response: error.response,
            ),
          );
        } else if (statusCode != null && statusCode >= 500) {
          handler.reject(
            DioException(
              requestOptions: error.requestOptions,
              error: ServerException(message, statusCode: statusCode),
              type: error.type,
              response: error.response,
            ),
          );
        } else if (error.type == DioExceptionType.connectionError ||
            error.type == DioExceptionType.connectionTimeout) {
          handler.reject(
            DioException(
              requestOptions: error.requestOptions,
              error: NetworkException('Cannot connect to RAPID server at ${error.requestOptions.baseUrl}'),
              type: error.type,
            ),
          );
        } else {
          handler.next(error);
        }
      },
    ),
  );

  return dio;
}

String _extractMessage(DioException error) {
  try {
    final data = error.response?.data;
    if (data is Map && data.containsKey('detail')) return data['detail'].toString();
  } catch (_) {}
  return error.message ?? 'Unknown error';
}
