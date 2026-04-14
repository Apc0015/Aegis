import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/auth_provider.dart';
import 'widgets/db_pipeline_card.dart';
import 'widgets/eval_config_card.dart';
import 'widgets/llm_config_card.dart';
import 'widgets/rag_mode_selector.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSizes.paddingXL),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ──────────────────────────────────────────────────
            Text('Settings', style: AppTextStyles.displaySmall)
                .animate()
                .fadeIn(duration: 200.ms),
            const SizedBox(height: 4),
            Text('Configure LLM, retrieval, and evaluation settings',
                    style: AppTextStyles.bodySmall)
                .animate()
                .fadeIn(duration: 200.ms, delay: 50.ms),
            const SizedBox(height: 28),

            // ── User info ────────────────────────────────────────────────
            Container(
              padding: const EdgeInsets.all(AppSizes.paddingLG),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppSizes.radiusLG),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: AppColors.primaryLight,
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        (authState.userId ?? 'U')
                            .substring(0, 1)
                            .toUpperCase(),
                        style: AppTextStyles.headlineMedium
                            .copyWith(color: AppColors.primary),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(authState.userId ?? 'Unknown',
                          style: AppTextStyles.bodySmall
                              .copyWith(color: AppColors.textPrimary)),
                      Text(
                        authState.userRole?.toUpperCase() ?? '',
                        style: AppTextStyles.caption
                            .copyWith(color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                  const Spacer(),
                  OutlinedButton.icon(
                    onPressed: () =>
                        ref.read(authProvider.notifier).logout(),
                    icon: const Icon(Icons.logout, size: 14),
                    label: const Text('Sign out'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.error,
                      side:
                          BorderSide(color: AppColors.error.withOpacity(0.4)),
                    ),
                  ),
                ],
              ),
            ).animate().fadeIn(duration: 250.ms, delay: 100.ms),
            const SizedBox(height: 16),

            // ── LLM ─────────────────────────────────────────────────────
            const LlmConfigCard()
                .animate()
                .fadeIn(duration: 250.ms, delay: 120.ms),
            const SizedBox(height: 16),

            // ── RAG mode ─────────────────────────────────────────────────
            const RagModeSelector()
                .animate()
                .fadeIn(duration: 250.ms, delay: 140.ms),
            const SizedBox(height: 16),

            // ── DB pipeline ───────────────────────────────────────────────
            const DbPipelineCard()
                .animate()
                .fadeIn(duration: 250.ms, delay: 160.ms),
            const SizedBox(height: 16),

            // ── Evaluation ────────────────────────────────────────────────
            const EvalConfigCard()
                .animate()
                .fadeIn(duration: 250.ms, delay: 180.ms),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }
}
