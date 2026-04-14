import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

class StatsGrid extends StatelessWidget {
  final int totalDocuments;
  final int queriesToday;
  final double avgConfidence;
  final int avgLatencyMs;

  const StatsGrid({
    super.key,
    required this.totalDocuments,
    required this.queriesToday,
    required this.avgConfidence,
    required this.avgLatencyMs,
  });

  @override
  Widget build(BuildContext context) {
    final cards = [
      _StatCard(
        icon: Icons.description_outlined,
        label: 'Documents',
        value: totalDocuments.toString(),
        color: AppColors.primary,
      ),
      _StatCard(
        icon: Icons.query_stats_rounded,
        label: 'Queries Today',
        value: queriesToday.toString(),
        color: AppColors.info,
      ),
      _StatCard(
        icon: Icons.verified_outlined,
        label: 'Avg Confidence',
        value: '${(avgConfidence * 100).toStringAsFixed(0)}%',
        color: avgConfidence >= 0.7
            ? AppColors.highConf
            : avgConfidence >= 0.4
                ? AppColors.mediumConf
                : AppColors.lowConf,
      ),
      _StatCard(
        icon: Icons.timer_outlined,
        label: 'Avg Latency',
        value: '${avgLatencyMs}ms',
        color: AppColors.textSecondary,
      ),
    ];

    return LayoutBuilder(builder: (context, constraints) {
      final crossAxisCount = constraints.maxWidth > AppSizes.breakpointTablet ? 4 : 2;
      return GridView.count(
        crossAxisCount: crossAxisCount,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        childAspectRatio: constraints.maxWidth > AppSizes.breakpointTablet ? 2.0 : 1.8,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        children: cards,
      );
    });
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSizes.paddingLG),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSizes.radiusLG),
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label, style: AppTextStyles.bodySmall),
              Icon(icon, size: 16, color: color),
            ],
          ),
          Text(value,
              style: AppTextStyles.displaySmall.copyWith(
                  color: AppColors.textPrimary, height: 1.0)),
        ],
      ),
    );
  }
}
