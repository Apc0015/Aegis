import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../features/shell/shell_scaffold.dart';
import '../../features/auth/login_screen.dart';
import '../../features/dashboard/dashboard_screen.dart';
import '../../features/chat/chat_screen.dart';
import '../../features/documents/document_screen.dart';
import '../../features/projects/project_screen.dart';
import '../../features/audit/audit_screen.dart';
import '../../features/settings/settings_screen.dart';
import '../../providers/auth_provider.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final auth = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/dashboard',
    redirect: (context, state) {
      final isLoggedIn = auth.isAuthenticated;
      final isLoginPage = state.matchedLocation == '/login';

      if (!isLoggedIn && !isLoginPage) return '/login';
      if (isLoggedIn && isLoginPage) return '/dashboard';

      // Admin-only guard for audit page
      if (state.matchedLocation == '/audit' && auth.userRole != 'admin') {
        return '/dashboard';
      }
      return null;
    },
    routes: [
      // ── Public ─────────────────────────────────────────────────────────────
      GoRoute(
        path: '/login',
        builder: (_, __) => const LoginScreen(),
      ),

      // ── Authenticated shell ────────────────────────────────────────────────
      ShellRoute(
        builder: (_, __, child) => ShellScaffold(child: child),
        routes: [
          GoRoute(
            path: '/dashboard',
            builder: (_, __) => const DashboardScreen(),
          ),
          GoRoute(
            path: '/chat',
            builder: (_, __) => const ChatScreen(),
          ),
          GoRoute(
            path: '/chat/:projectId',
            builder: (_, state) => ChatScreen(
              initialProjectId: state.pathParameters['projectId'],
            ),
          ),
          GoRoute(
            path: '/documents',
            builder: (_, __) => const DocumentScreen(),
          ),
          GoRoute(
            path: '/projects',
            builder: (_, __) => const ProjectScreen(),
          ),
          GoRoute(
            path: '/audit',
            builder: (_, __) => const AuditScreen(),
          ),
          GoRoute(
            path: '/settings',
            builder: (_, __) => const SettingsScreen(),
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Text('Page not found: ${state.uri}'),
      ),
    ),
  );
});
