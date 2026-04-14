import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/auth_provider.dart';
import '../../providers/project_provider.dart';
import '../../providers/health_provider.dart';
import '../../shared/widgets/rapid_logo.dart';
import '../../shared/widgets/role_badge.dart';

class TopBar extends ConsumerWidget {
  const TopBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final activeProject = ref.watch(activeProjectProvider);
    final healthAsync = ref.watch(healthProvider);
    final width = MediaQuery.of(context).size.width;
    final isNarrow = width < AppSizes.tabletBreak;

    return Container(
      height: AppSizes.topBarHeight,
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(bottom: BorderSide(color: AppColors.border, width: 1)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          // Hamburger on narrow screens
          if (isNarrow) ...[
            Builder(
              builder: (ctx) => IconButton(
                icon: const Icon(Icons.menu_rounded,
                    size: 20, color: AppColors.textSecondary),
                onPressed: () => Scaffold.of(ctx).openDrawer(),
                tooltip: 'Menu',
                padding: EdgeInsets.zero,
              ),
            ),
            const SizedBox(width: 8),
          ],

          // Logo (hidden on narrow if sidebar is shown)
          if (!isNarrow) const RapidLogo(),
          if (!isNarrow) const SizedBox(width: 16),

          // Active project chip
          if (activeProject != null) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.primaryLight,
                borderRadius: BorderRadius.circular(AppSizes.radiusFull),
                border: Border.all(color: AppColors.primaryBorder),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.folder_outlined,
                      size: 13, color: AppColors.primary),
                  const SizedBox(width: 4),
                  Text(
                    activeProject.projectName,
                    style: AppTextStyles.labelSmall.copyWith(
                      color: AppColors.primary, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
          ],

          const Spacer(),

          // Health indicator dot
          healthAsync.when(
            data: (h) => _HealthDot(isOk: h.isOk, label: h.message),
            loading: () => const _HealthDot(isOk: null),
            error: (_, __) => const _HealthDot(isOk: false, label: 'Server unreachable'),
          ),

          const SizedBox(width: 12),

          // Role badge
          if (auth.userRole != null) RoleBadge(role: auth.userRole!),
        ],
      ),
    );
  }
}

class _HealthDot extends StatelessWidget {
  final bool? isOk;
  final String? label;
  const _HealthDot({this.isOk, this.label});

  @override
  Widget build(BuildContext context) {
    final color = isOk == null
        ? AppColors.textMuted
        : isOk!
            ? AppColors.success
            : AppColors.error;

    return Tooltip(
      message: label ?? (isOk == null ? 'Checking…' : isOk! ? 'All systems operational' : 'Server error'),
      child: Container(
        width: 8, height: 8,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          boxShadow: isOk == true
              ? [BoxShadow(color: color.withOpacity(0.4), blurRadius: 4, spreadRadius: 1)]
              : null,
        ),
      ),
    );
  }
}
