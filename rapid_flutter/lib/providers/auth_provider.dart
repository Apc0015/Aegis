import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/datasources/rapid_api_datasource.dart';
import '../data/models/auth_models.dart';
import '../core/network/api_client.dart';
import 'api_provider.dart';

// ── Auth State ───────────────────────────────────────────────────────────────
class AuthState {
  final String? token;
  final String? userId;
  final String? userRole;
  final bool isLoading;
  final String? error;

  const AuthState({
    this.token,
    this.userId,
    this.userRole,
    this.isLoading = false,
    this.error,
  });

  bool get isAuthenticated => token != null;

  AuthState copyWith({
    String? token,
    String? userId,
    String? userRole,
    bool? isLoading,
    String? error,
    bool clearToken = false,
    bool clearError = false,
  }) =>
      AuthState(
        token: clearToken ? null : (token ?? this.token),
        userId: clearToken ? null : (userId ?? this.userId),
        userRole: clearToken ? null : (userRole ?? this.userRole),
        isLoading: isLoading ?? this.isLoading,
        error: clearError ? null : (error ?? this.error),
      );
}

// ── AuthNotifier ─────────────────────────────────────────────────────────────
class AuthNotifier extends StateNotifier<AuthState> {
  final RapidApiDataSource _api;

  AuthNotifier(this._api) : super(const AuthState()) {
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    final token = await getStoredToken();
    if (token != null && token.isNotEmpty) {
      // Decode userId/userRole from JWT payload (simple base64 decode, no verification needed)
      try {
        final parts = token.split('.');
        if (parts.length == 3) {
          final payload = _decodeBase64(parts[1]);
          final sub = payload['sub'] as String?;
          final role = payload['role'] as String?;
          if (sub != null && role != null) {
            state = AuthState(token: token, userId: sub, userRole: role);
            return;
          }
        }
      } catch (_) {}
    }
  }

  Map<String, dynamic> _decodeBase64(String encoded) {
    String normalized = encoded.replaceAll('-', '+').replaceAll('_', '/');
    while (normalized.length % 4 != 0) normalized += '=';
    final bytes = base64Decode(normalized);
    final decoded = utf8.decode(bytes);
    return jsonDecode(decoded) as Map<String, dynamic>;
  }

  Future<bool> login(String username, String password) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final token = await _api.login(username, password);
      await storeToken(token.accessToken);
      state = AuthState(
        token: token.accessToken,
        userId: token.userId,
        userRole: token.userRole,
      );
      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _errorMsg(e));
      return false;
    }
  }

  Future<void> logout() async {
    await clearToken();
    state = const AuthState();
  }

  String _errorMsg(Object e) {
    final s = e.toString();
    if (s.contains('401')) return 'Incorrect username or password';
    if (s.contains('connect')) return 'Cannot reach RAPID server';
    return s;
  }
}

// ── Providers ────────────────────────────────────────────────────────────────
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.watch(apiDataSourceProvider));
});
