import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

class RoutingPathBadge extends StatelessWidget {
  final String routingPath;
  const RoutingPathBadge({super.key, required this.routingPath});

  @override
  Widget build(BuildContext context) {
    if (routingPath == 'direct') return const SizedBox.shrink();

    final (Color color, String label, IconData icon) = switch (routingPath) {
      'web'        => (AppColors.routeWeb,        'Web-supplemented',    Icons.language_outlined),
      'disclaimer' => (AppColors.routeDisclaimer, 'Low confidence',      Icons.info_outline_rounded),
      'refuse'     => (AppColors.routeRefuse,     'Cannot answer',       Icons.block_outlined),
      'denied'     => (AppColors.routeDenied,     'Access denied',       Icons.lock_outline_rounded),
      _            => (AppColors.textMuted,        routingPath,           Icons.circle_outlined),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(AppSizes.radiusFull),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 10, color: color),
          const SizedBox(width: 4),
          Text(label,
              style: AppTextStyles.labelSmall
                  .copyWith(color: color, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
