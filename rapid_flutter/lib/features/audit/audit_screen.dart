import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/audit_provider.dart';
import '../../shared/widgets/error_banner.dart';
import 'widgets/audit_table.dart';
import 'widgets/export_button.dart';

class AuditScreen extends ConsumerWidget {
  const AuditScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auditAsync = ref.watch(auditProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSizes.paddingXL),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1200),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ──────────────────────────────────────────────────
            Row(
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Audit Log', style: AppTextStyles.displaySmall),
                    const SizedBox(height: 4),
                    Text('Query history and access decisions',
                        style: AppTextStyles.bodySmall),
                  ],
                ),
                const Spacer(),
                const ExportButton(),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () => ref.invalidate(auditProvider),
                  icon: const Icon(Icons.refresh, size: 14),
                  label: Text('Refresh',
                      style: AppTextStyles.labelSmall),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ).animate().fadeIn(duration: 200.ms),
            const SizedBox(height: 28),

            // ── Table ────────────────────────────────────────────────────
            auditAsync.when(
              loading: () => const Center(
                  child: CircularProgressIndicator(strokeWidth: 2)),
              error: (e, _) => ErrorBanner(message: e.toString()),
              data: (records) => AuditTable(records: records)
                  .animate()
                  .fadeIn(duration: 250.ms, delay: 100.ms),
            ),
          ],
        ),
      ),
    );
  }
}
