import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../providers/health_provider.dart';

class HealthStatusCard extends ConsumerWidget {
  const HealthStatusCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final healthAsync = ref.watch(healthProvider);

    return Container(
      padding: const EdgeInsets.all(AppSizes.paddingLG),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSizes.radiusLG),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.monitor_heart_outlined,
                  size: 16, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Text('System Health', style: AppTextStyles.headlineSmall),
              const Spacer(),
              TextButton(
                onPressed: () => ref.invalidate(healthProvider),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: Text('Refresh',
                    style: AppTextStyles.labelSmall
                        .copyWith(color: AppColors.primary)),
              ),
            ],
          ),
          const SizedBox(height: 16),
          healthAsync.when(
            loading: () => const _LoadingRows(),
            error: (e, _) => _ErrorRow(message: e.toString()),
            data: (health) => Column(
              children: [
                _StatusRow(
                  label: 'LLM Provider',
                  value: health.llmProvider,
                  ok: health.status == 'ok',
                ),
                const SizedBox(height: 10),
                _StatusRow(
                  label: 'Embedding',
                  value: health.embedProvider,
                  ok: health.status == 'ok',
                ),
                const SizedBox(height: 10),
                _StatusRow(
                  label: 'Vector Store',
                  value: health.dbConnected ? 'Connected' : 'Unavailable',
                  ok: health.dbConnected,
                ),
                const SizedBox(height: 10),
                _StatusRow(
                  label: 'API Version',
                  value: health.version,
                  ok: true,
                  neutral: true,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusRow extends StatelessWidget {
  final String label;
  final String value;
  final bool ok;
  final bool neutral;

  const _StatusRow({
    required this.label,
    required this.value,
    required this.ok,
    this.neutral = false,
  });

  @override
  Widget build(BuildContext context) {
    final dotColor = neutral
        ? AppColors.textMuted
        : ok
            ? AppColors.highConf
            : AppColors.lowConf;

    return Row(
      children: [
        Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(
            color: dotColor,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 10),
        Text(label, style: AppTextStyles.bodySmall),
        const Spacer(),
        Text(value,
            style:
                AppTextStyles.labelSmall.copyWith(color: AppColors.textSecondary)),
      ],
    );
  }
}

class _LoadingRows extends StatelessWidget {
  const _LoadingRows();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(
        4,
        (_) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Row(
            children: [
              Container(
                width: 7, height: 7,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 10),
              Container(
                width: 80, height: 12,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorRow extends StatelessWidget {
  final String message;
  const _ErrorRow({required this.message});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.error_outline, size: 14, color: AppColors.error),
        const SizedBox(width: 8),
        Expanded(
          child: Text('Health check failed',
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.error)),
        ),
      ],
    );
  }
}
