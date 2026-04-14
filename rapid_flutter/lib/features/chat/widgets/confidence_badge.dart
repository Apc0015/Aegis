import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

class ConfidenceBadge extends StatelessWidget {
  final String verdict;
  final double confidence;

  const ConfidenceBadge({
    super.key,
    required this.verdict,
    required this.confidence,
  });

  @override
  Widget build(BuildContext context) {
    final (Color text, Color bg, Color border, IconData icon) = switch (verdict) {
      'high'   => (AppColors.highText,   AppColors.highBg,   AppColors.highBorder,   Icons.check_circle_outline_rounded),
      'medium' => (AppColors.mediumText, AppColors.mediumBg, AppColors.mediumBorder, Icons.warning_amber_rounded),
      _        => (AppColors.lowText,    AppColors.lowBg,    AppColors.lowBorder,    Icons.error_outline_rounded),
    };

    final pct = (confidence * 100).toStringAsFixed(0);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSizes.radiusFull),
        border: Border.all(color: border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: text),
          const SizedBox(width: 4),
          Text(
            '${verdict[0].toUpperCase()}${verdict.substring(1)} confidence · $pct%',
            style: AppTextStyles.labelSmall.copyWith(
                color: text, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
