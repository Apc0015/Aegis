import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../data/models/audit_models.dart';
import '../../../providers/audit_provider.dart';

class RecentActivityList extends ConsumerWidget {
  const RecentActivityList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auditAsync = ref.watch(auditProvider);

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSizes.radiusLG),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSizes.paddingLG),
            child: Row(
              children: [
                const Icon(Icons.history_rounded,
                    size: 16, color: AppColors.textSecondary),
                const SizedBox(width: 8),
                Text('Recent Activity', style: AppTextStyles.headlineSmall),
              ],
            ),
          ),
          const Divider(height: 1),
          auditAsync.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(AppSizes.paddingLG),
              child: Center(
                  child: CircularProgressIndicator(strokeWidth: 2)),
            ),
            error: (e, _) => Padding(
              padding: const EdgeInsets.all(AppSizes.paddingLG),
              child: Text('Could not load activity',
                  style: AppTextStyles.bodySmall
                      .copyWith(color: AppColors.error)),
            ),
            data: (records) {
              if (records.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.all(AppSizes.paddingXL),
                  child: Center(
                    child: Text('No activity yet',
                        style: AppTextStyles.bodySmall),
                  ),
                );
              }
              final recent = records.take(10).toList();
              return ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: recent.length,
                separatorBuilder: (_, __) =>
                    const Divider(height: 1),
                itemBuilder: (_, i) => _ActivityTile(record: recent[i]),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _ActivityTile extends StatelessWidget {
  final AuditRecord record;
  const _ActivityTile({required this.record});

  Color _verdictColor(String? verdict) {
    switch (verdict?.toLowerCase()) {
      case 'high':
        return AppColors.highConf;
      case 'medium':
        return AppColors.mediumConf;
      case 'low':
        return AppColors.lowConf;
      default:
        return AppColors.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
          horizontal: AppSizes.paddingLG, vertical: 10),
      child: Row(
        children: [
          Container(
            width: 7, height: 7,
            decoration: BoxDecoration(
              color: _verdictColor(record.verdict),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record.query.length > 80
                      ? '${record.query.substring(0, 80)}…'
                      : record.query,
                  style: AppTextStyles.bodySmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  '${record.userId} · ${record.projectId ?? '—'}',
                  style: AppTextStyles.caption,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            record.verdict?.toUpperCase() ?? '—',
            style: AppTextStyles.labelSmall
                .copyWith(color: _verdictColor(record.verdict)),
          ),
        ],
      ),
    );
  }
}
