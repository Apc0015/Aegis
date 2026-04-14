import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../providers/settings_provider.dart';

class RagModeSelector extends ConsumerWidget {
  const RagModeSelector({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsProvider);
    final notifier = ref.read(settingsProvider.notifier);

    const modes = [
      ('auto', 'Auto', 'Let RAPID decide the best retrieval strategy'),
      ('vector', 'Vector', 'Semantic similarity search only (embedding model)'),
      ('bm25', 'BM25', 'Keyword search only — faster, no embedding'),
      ('hybrid', 'Hybrid', 'Vector + BM25 fused with Reciprocal Rank Fusion'),
    ];

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
              const Icon(Icons.manage_search_rounded,
                  size: 16, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Text('RAG Mode', style: AppTextStyles.headlineSmall),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: modes
                .map((m) => _ModeChip(
                      value: m.$1,
                      label: m.$2,
                      description: m.$3,
                      selected: settings.ragMode == m.$1,
                      onSelected: () => notifier.setRagMode(m.$1),
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  final String value;
  final String label;
  final String description;
  final bool selected;
  final VoidCallback onSelected;

  const _ModeChip({
    required this.value,
    required this.label,
    required this.description,
    required this.selected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onSelected,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 180,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected ? AppColors.primaryLight : AppColors.surfaceVariant,
          borderRadius: BorderRadius.circular(AppSizes.radiusMD),
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  label,
                  style: AppTextStyles.headlineSmall.copyWith(
                    color:
                        selected ? AppColors.primary : AppColors.textPrimary,
                  ),
                ),
                const Spacer(),
                if (selected)
                  Icon(Icons.check_circle_rounded,
                      size: 14, color: AppColors.primary),
              ],
            ),
            const SizedBox(height: 4),
            Text(description,
                style: AppTextStyles.caption, maxLines: 2,
                overflow: TextOverflow.ellipsis),
          ],
        ),
      ),
    );
  }
}
