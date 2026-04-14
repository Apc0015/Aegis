import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../data/models/query_models.dart';

class FeaturePillsRow extends StatelessWidget {
  final QueryResult result;
  const FeaturePillsRow({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final pills = <(IconData, String, Color)>[];

    if (result.webUsed)
      pills.add((Icons.language_outlined, 'Web search', AppColors.info));
    if (result.crossModelEval)
      pills.add((Icons.compare_arrows_rounded, 'Cross-model eval', AppColors.primary));
    if (result.rerankerUsed)
      pills.add((Icons.sort_rounded, 'Reranked', AppColors.textSecondary));
    if (result.dbTriggered)
      pills.add((Icons.storage_outlined, 'DB pipeline', AppColors.textSecondary));
    if (result.columnsBlocked.isNotEmpty)
      pills.add((Icons.visibility_off_outlined,
          '${result.columnsBlocked.length} field${result.columnsBlocked.length > 1 ? 's' : ''} restricted',
          AppColors.warning));

    if (pills.isEmpty) return const SizedBox.shrink();

    return Wrap(
      spacing: 6,
      runSpacing: 4,
      children: pills.map((p) => _Pill(icon: p.$1, label: p.$2, color: p.$3)).toList(),
    );
  }
}

class _Pill extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _Pill({required this.icon, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.surfaceVariant,
        borderRadius: BorderRadius.circular(AppSizes.radiusFull),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 10, color: color),
          const SizedBox(width: 4),
          Text(label, style: AppTextStyles.labelSmall.copyWith(color: color)),
        ],
      ),
    );
  }
}
