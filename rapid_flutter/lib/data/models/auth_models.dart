class LoginRequest {
  final String username;
  final String password;
  const LoginRequest({required this.username, required this.password});
}

class AuthToken {
  final String accessToken;
  final String userId;
  final String userRole;
  final int expiresIn;

  const AuthToken({
    required this.accessToken,
    required this.userId,
    required this.userRole,
    required this.expiresIn,
  });

  factory AuthToken.fromJson(Map<String, dynamic> j) => AuthToken(
    accessToken: j['access_token'] as String,
    userId: j['user_id'] as String,
    userRole: j['user_role'] as String,
    expiresIn: j['expires_in'] as int,
  );
}
