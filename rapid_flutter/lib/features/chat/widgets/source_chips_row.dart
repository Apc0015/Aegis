import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../data/models/query_models.dart';

class SourceChipsRow extends StatefulWidget {
  final List<SourceChunk> sources;
  const SourceChipsRow({super.key, required this.sources});

  @override
  State<SourceChipsRow> createState() => _SourceChipsRowState();
}

class _SourceChipsRowState extends State<SourceChipsRow> {
  int? _expanded;

  @override
  Widget build(BuildContext context) {
    if (widget.sources.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 6, runSpacing: 4,
          children: List.generate(widget.sources.length, (i) {
            final src = widget.sources[i];
            final isExpanded = _expanded == i;
            return ActionChip(
              label: Text(
                '📄 ${src.source} · chunk ${src.chunkIndex}',
                style: AppTextStyles.labelSmall.copyWith(
                    color: isExpanded ? AppColors.primary : AppColors.textSecondary),
              ),
              backgroundColor: isExpanded
                  ? AppColors.primaryLight
                  : AppColors.surfaceVariant,
              side: BorderSide(
                  color: isExpanded ? AppColors.primaryBorder : AppColors.border),
              padding: const EdgeInsets.symmetric(horizontal: 4),
              visualDensity: VisualDensity.compact,
              onPressed: () =>
                  setState(() => _expanded = isExpanded ? null : i),
            );
          }),
        ),
        if (_expanded != null) ...[
          const SizedBox(height: 8),
          _SourceCard(chunk: widget.sources[_expanded!]),
        ],
      ],
    );
  }
}

class _SourceCard extends StatelessWidget {
  final SourceChunk chunk;
  const _SourceCard({required this.chunk});

  @override
  Widget build(BuildContext context) {
    final preview = chunk.text.length > 300
        ? '${chunk.text.substring(0, 300)}…'
        : chunk.text;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.primaryLight,
        borderRadius: BorderRadius.circular(AppSizes.radiusMD),
        border: Border.all(color: AppColors.primaryBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.description_outlined,
                size: 13, color: AppColors.primary),
            const SizedBox(width: 6),
            Text(
              '${chunk.source} · chunk ${chunk.chunkIndex}',
              style: AppTextStyles.labelSmall
                  .copyWith(color: AppColors.primary, fontWeight: FontWeight.w600),
            ),
          ]),
          const SizedBox(height: 6),
          Text(preview,
              style: AppTextStyles.bodySmall
                  .copyWith(color: AppColors.textPrimary, height: 1.5)),
        ],
      ),
    );
  }
}
