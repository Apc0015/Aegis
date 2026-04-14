import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/auth_provider.dart';
import '../../shared/widgets/rapid_logo.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final ok = await ref.read(authProvider.notifier).login(
      _usernameCtrl.text.trim(),
      _passwordCtrl.text,
    );
    if (ok && mounted) context.go('/dashboard');
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSizes.paddingLG),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // ── Logo + tagline ─────────────────────────────────────────────
                const Center(child: RapidLogo()),
                const SizedBox(height: 8),
                Text(
                  'Enterprise RAG · Private · Instant',
                  textAlign: TextAlign.center,
                  style: AppTextStyles.bodySmall,
                ),
                const SizedBox(height: 40),

                // ── Card ───────────────────────────────────────────────────────
                Container(
                  padding: const EdgeInsets.all(AppSizes.paddingXL),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(AppSizes.radiusXL),
                    border: Border.all(color: AppColors.border),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.04),
                        blurRadius: 16, offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text('Sign in', style: AppTextStyles.displaySmall),
                        const SizedBox(height: 4),
                        Text('Access your RAPID workspace',
                            style: AppTextStyles.bodySmall),
                        const SizedBox(height: 28),

                        // Username
                        TextFormField(
                          controller: _usernameCtrl,
                          decoration: const InputDecoration(
                            labelText: 'Username',
                            prefixIcon: Icon(Icons.person_outline_rounded),
                          ),
                          textInputAction: TextInputAction.next,
                          autofillHints: const [AutofillHints.username],
                          validator: (v) =>
                              v == null || v.isEmpty ? 'Enter username' : null,
                        ),
                        const SizedBox(height: 16),

                        // Password
                        TextFormField(
                          controller: _passwordCtrl,
                          obscureText: _obscure,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline_rounded),
                            suffixIcon: IconButton(
                              icon: Icon(_obscure
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined),
                              onPressed: () =>
                                  setState(() => _obscure = !_obscure),
                            ),
                          ),
                          textInputAction: TextInputAction.done,
                          onFieldSubmitted: (_) => _submit(),
                          autofillHints: const [AutofillHints.password],
                          validator: (v) =>
                              v == null || v.isEmpty ? 'Enter password' : null,
                        ),

                        // Error message
                        if (auth.error != null) ...[
                          const SizedBox(height: 12),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 8),
                            decoration: BoxDecoration(
                              color: AppColors.errorBg,
                              borderRadius:
                                  BorderRadius.circular(AppSizes.radiusMD),
                              border:
                                  Border.all(color: AppColors.error.withOpacity(0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline_rounded,
                                    size: 14, color: AppColors.error),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(auth.error!,
                                      style: AppTextStyles.bodySmall.copyWith(
                                          color: AppColors.error)),
                                ),
                              ],
                            ),
                          ),
                        ],

                        const SizedBox(height: 24),

                        // Sign in button
                        SizedBox(
                          height: 44,
                          child: ElevatedButton(
                            onPressed: auth.isLoading ? null : _submit,
                            child: auth.isLoading
                                ? const SizedBox(
                                    width: 18, height: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2, color: Colors.white),
                                  )
                                : const Text('Sign in'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ).animate().fadeIn(duration: 300.ms).slideY(begin: 0.04),

                const SizedBox(height: 24),
                Text(
                  'RAPID v1.0 · All queries are audited',
                  textAlign: TextAlign.center,
                  style: AppTextStyles.caption,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
