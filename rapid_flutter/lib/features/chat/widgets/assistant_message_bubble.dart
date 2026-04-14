import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../data/models/query_models.dart';
import 'confidence_badge.dart';
import 'routing_path_badge.dart';
import 'feature_pills_row.dart';
import 'source_chips_row.dart';

/// Renders a complete assistant message with all metadata.
/// Layout (top → bottom):
///   ConfidenceBadge | RoutingPathBadge
///   [DisclaimerBanner] (if disclaimer)
///   [AccessDeniedCard / RefusalCard] OR [MarkdownBody]
///   FeaturePillsRow
///   SourceChipsRow
///   MetadataFooter
class AssistantMessageBubble extends StatelessWidget {
  final QueryResult result;
  const AssistantMessageBubble({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: AppSizes.bubbleMaxWidth),
      margin: const EdgeInsets.only(bottom: 20),
      padding: const EdgeInsets.all(AppSizes.bubblePadH),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(4),
          topRight: Radius.circular(AppSizes.radiusLG),
          bottomLeft: Radius.circular(AppSizes.radiusLG),
          bottomRight: Radius.circular(AppSizes.radiusLG),
        ),
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8, offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header row: badges ─────────────────────────────────────────────
          Wrap(
            spacing: 6, runSpacing: 4,
            children: [
              ConfidenceBadge(
                  verdict: result.verdict, confidence: result.confidence),
              RoutingPathBadge(routingPath: result.routingPath),
            ],
          ),
          const SizedBox(height: 10),

          // ── Disclaimer banner ──────────────────────────────────────────────
          if (result.routingPath == 'disclaimer') ...[
            _DisclaimerBanner(),
            const SizedBox(height: 10),
          ],

          // ── Access denied or refusal ───────────────────────────────────────
          if (result.routingPath == 'denied')
            _AccessDeniedCard(reason: result.accessDecision.denialReason)
          else if (result.routingPath == 'refuse')
            _RefusalCard()
          else ...[
            // ── Answer (markdown) ────────────────────────────────────────────
            MarkdownBody(
              data: result.answer,
              styleSheet: MarkdownStyleSheet(
                p: AppTextStyles.bodyMedium,
                h1: AppTextStyles.headlineLarge,
                h2: AppTextStyles.headlineMedium,
                h3: AppTextStyles.headlineSmall,
                code: AppTextStyles.mono.copyWith(
                  backgroundColor: AppColors.surfaceVariant,
                ),
                blockquoteDecoration: BoxDecoration(
                  color: AppColors.surfaceVariant,
                  border: const Border(
                      left: BorderSide(color: AppColors.primary, width: 3)),
                ),
              ),
            ),
            const SizedBox(height: 12),

            // ── Feature pills ────────────────────────────────────────────────
            FeaturePillsRow(result: result),
            if (result.webUsed ||
                result.crossModelEval ||
                result.rerankerUsed ||
                result.dbTriggered ||
                result.columnsBlocked.isNotEmpty)
              const SizedBox(height: 8),

            // ── Sources ──────────────────────────────────────────────────────
            SourceChipsRow(sources: result.sources),
            if (result.sources.isNotEmpty) const SizedBox(height: 8),
          ],

          // ── Metadata footer ────────────────────────────────────────────────
          const Divider(height: 16),
          _MetadataFooter(result: result),
        ],
      ),
    ).animate().fadeIn(duration: 200.ms).slideY(begin: 0.03);
  }
}

class _DisclaimerBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.warningBg,
        borderRadius: BorderRadius.circular(AppSizes.radiusMD),
        border: Border.all(color: AppColors.warning.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded,
              size: 14, color: AppColors.warning),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Low confidence — this answer may be incomplete. Verify with authoritative sources.',
              style: AppTextStyles.bodySmall
                  .copyWith(color: AppColors.mediumText),
            ),
          ),
        ],
      ),
    );
  }
}

class _AccessDeniedCard extends StatelessWidget {
  final String? reason;
  const _AccessDeniedCard({this.reason});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Color(0xFFFDF4FF),
        borderRadius: BorderRadius.circular(AppSizes.radiusMD),
        border: Border.all(color: AppColors.routeDenied.withOpacity(0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.lock_outline_rounded,
              size: 18, color: AppColors.routeDenied),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Access Denied',
                    style: AppTextStyles.headlineSmall
                        .copyWith(color: AppColors.routeDenied)),
                const SizedBox(height: 4),
                Text(
                  reason ?? 'You do not have permission to access this information.',
                  style: AppTextStyles.bodySmall.copyWith(
                      color: AppColors.routeDenied.withOpacity(0.8)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RefusalCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.errorBg,
        borderRadius: BorderRadius.circular(AppSizes.radiusMD),
        border: Border.all(color: AppColors.error.withOpacity(0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.search_off_rounded,
              size: 18, color: AppColors.error),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Not Found in Documents',
                    style: AppTextStyles.headlineSmall
                        .copyWith(color: AppColors.error)),
                const SizedBox(height: 4),
                Text(
                  'Insufficient information was found in the indexed documents to answer this question.',
                  style: AppTextStyles.bodySmall
                      .copyWith(color: AppColors.error.withOpacity(0.8)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetadataFooter extends StatelessWidget {
  final QueryResult result;
  const _MetadataFooter({required this.result});

  @override
  Widget build(BuildContext context) {
    final parts = <String>[];
    if (result.latencyMs > 0) parts.add('${result.latencyMs}ms');
    if (result.modelUsed.isNotEmpty) parts.add(result.modelUsed);
    if (result.chunksUsed > 0) parts.add('${result.chunksUsed} chunks');

    return Text(
      parts.join(' · '),
      style: AppTextStyles.caption,
    );
  }
}
