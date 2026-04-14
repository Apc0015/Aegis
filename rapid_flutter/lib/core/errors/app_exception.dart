/// Typed exceptions for the RAPID Flutter client.
class AppException implements Exception {
  final String message;
  final int? statusCode;

  const AppException(this.message, {this.statusCode});

  @override
  String toString() => 'AppException($statusCode): $message';
}

class AuthException extends AppException {
  const AuthException(super.message) : super(statusCode: 401);
}

class ForbiddenException extends AppException {
  const ForbiddenException(super.message) : super(statusCode: 403);
}

class NetworkException extends AppException {
  const NetworkException(super.message);
}

class ServerException extends AppException {
  const ServerException(super.message, {super.statusCode});
}

class ValidationException extends AppException {
  const ValidationException(super.message) : super(statusCode: 422);
}
