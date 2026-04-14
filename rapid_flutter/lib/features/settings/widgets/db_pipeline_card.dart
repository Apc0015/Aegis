import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../providers/settings_provider.dart';

class DbPipelineCard extends ConsumerWidget {
  const DbPipelineCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsProvider);
    final notifier = ref.read(settingsProvider.notifier);

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
              const Icon(Icons.storage_outlined,
                  size: 16, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Text('Data Pipeline', style: AppTextStyles.headlineSmall),
            ],
          ),
          const SizedBox(height: 16),
          _ToggleRow(
            label: 'Force DB pipeline',
            description:
                'Always run the structured database pipeline regardless of query type',
            value: settings.forceDb,
            onChanged: (v) => notifier.setForceDb(v),
          ),
          const Divider(height: 24),
          _ToggleRow(
            label: 'Web search supplement',
            description:
                'Allow the agent to perform web searches when local docs are insufficient',
            value: settings.webEnabled,
            onChanged: (v) => notifier.setWebEnabled(v),
          ),
          const Divider(height: 24),
          _ToggleRow(
            label: 'Reranker',
            description:
                'Apply cross-encoder reranker to retrieved chunks for better accuracy',
            value: settings.rerankerEnabled,
            onChanged: (v) => notifier.setRerankerEnabled(v),
          ),
        ],
      ),
    );
  }
}

class _ToggleRow extends StatelessWidget {
  final String label;
  final String description;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _ToggleRow({
    required this.label,
    required this.description,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: AppTextStyles.bodySmall
                      .copyWith(color: AppColors.textPrimary)),
              const SizedBox(height: 2),
              Text(description, style: AppTextStyles.caption),
            ],
          ),
        ),
        const SizedBox(width: 16),
        Switch(
          value: value,
          onChanged: onChanged,
          activeColor: AppColors.primary,
        ),
      ],
    );
  }
}
