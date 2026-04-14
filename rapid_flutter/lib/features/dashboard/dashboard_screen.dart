import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/audit_provider.dart';
import '../../providers/document_provider.dart';
import '../../providers/health_provider.dart';
import 'widgets/confidence_donut_chart.dart';
import 'widgets/health_status_card.dart';
import 'widgets/recent_activity_list.dart';
import 'widgets/stats_grid.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auditAsync = ref.watch(auditProvider);
    final docsAsync = ref.watch(documentsProvider);

    // Compute stats from audit records
    final records = auditAsync.valueOrNull ?? [];
    final docs = docsAsync.valueOrNull ?? [];

    final now = DateTime.now();
    final todayRecords = records.where((r) {
      try {
        final d = DateTime.parse(r.timestamp);
        return d.year == now.year &&
            d.month == now.month &&
            d.day == now.day;
      } catch (_) {
        return false;
      }
    }).toList();

    double avgConf = 0;
    int avgLatency = 0;
    int high = 0, medium = 0, low = 0;

    if (records.isNotEmpty) {
      for (final r in records) {
        switch (r.verdict?.toLowerCase()) {
          case 'high':
            high++;
            break;
          case 'medium':
            medium++;
            break;
          case 'low':
            low++;
            break;
        }
        avgConf += r.confidence ?? 0;
        avgLatency += r.latencyMs ?? 0;
      }
      avgConf /= records.length;
      avgLatency ~/= records.length;
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSizes.paddingXL),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1200),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ──────────────────────────────────────────────────────
            Text('Dashboard', style: AppTextStyles.displaySmall)
                .animate()
                .fadeIn(duration: 200.ms),
            const SizedBox(height: 4),
            Text('System overview and recent activity',
                    style: AppTextStyles.bodySmall)
                .animate()
                .fadeIn(duration: 200.ms, delay: 50.ms),
            const SizedBox(height: 28),

            // ── Stats ────────────────────────────────────────────────────────
            StatsGrid(
              totalDocuments: docs.length,
              queriesToday: todayRecords.length,
              avgConfidence: avgConf,
              avgLatencyMs: avgLatency,
            ).animate().fadeIn(duration: 250.ms, delay: 100.ms),
            const SizedBox(height: 20),

            // ── Health + Donut ───────────────────────────────────────────────
            LayoutBuilder(builder: (context, constraints) {
              final wide = constraints.maxWidth > AppSizes.breakpointTablet;
              if (wide) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Expanded(child: HealthStatusCard()),
                    const SizedBox(width: 16),
                    Expanded(
                      child: ConfidenceDonutChart(
                          high: high, medium: medium, low: low),
                    ),
                  ],
                ).animate().fadeIn(duration: 250.ms, delay: 150.ms);
              }
              return Column(
                children: [
                  const HealthStatusCard(),
                  const SizedBox(height: 16),
                  ConfidenceDonutChart(
                      high: high, medium: medium, low: low),
                ],
              ).animate().fadeIn(duration: 250.ms, delay: 150.ms);
            }),
            const SizedBox(height: 20),

            // ── Recent activity ──────────────────────────────────────────────
            const RecentActivityList()
                .animate()
                .fadeIn(duration: 250.ms, delay: 200.ms),
          ],
        ),
      ),
    );
  }
}
