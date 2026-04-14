import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/auth_provider.dart';
import '../../shared/widgets/rapid_logo.dart';

class _NavItem {
  final String path;
  final IconData icon;
  final String label;
  final bool adminOnly;

  const _NavItem(this.path, this.icon, this.label, {this.adminOnly = false});
}

const _navItems = [
  _NavItem('/dashboard', Icons.grid_view_rounded, 'Dashboard'),
  _NavItem('/chat', Icons.chat_bubble_outline_rounded, 'Chat'),
  _NavItem('/documents', Icons.description_outlined, 'Documents'),
  _NavItem('/projects', Icons.folder_outlined, 'Projects'),
  _NavItem('/audit', Icons.security_outlined, 'Audit Log', adminOnly: true),
  _NavItem('/settings', Icons.tune_outlined, 'Settings'),
];

class SidebarNav extends ConsumerWidget {
  final bool isDrawer;
  const SidebarNav({super.key, this.isDrawer = false});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final location = GoRouterState.of(context).matchedLocation;

    Widget nav = Container(
      width: AppSizes.sidebarWidth,
      decoration: const BoxDecoration(
        color: AppColors.sidebarBg,
        border: Border(
          right: BorderSide(color: AppColors.sidebarBorder, width: 1),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (isDrawer) ...[
            const SizedBox(height: 24),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 20),
              child: RapidLogo(),
            ),
            const SizedBox(height: 16),
            const Divider(color: AppColors.border, height: 1),
          ],
          const SizedBox(height: 8),
          // Nav items
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              children: _navItems
                  .where((item) => !item.adminOnly || auth.userRole == 'admin')
                  .map((item) => _NavTile(
                        item: item,
                        isSelected: location.startsWith(item.path),
                      ))
                  .toList(),
            ),
          ),
          // Bottom: user info
          const Divider(color: AppColors.border, height: 1),
          _UserFooter(auth: auth),
        ],
      ),
    );

    return nav;
  }
}

class _NavTile extends StatelessWidget {
  final _NavItem item;
  final bool isSelected;

  const _NavTile({required this.item, required this.isSelected});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => context.go(item.path),
          borderRadius: BorderRadius.circular(AppSizes.radiusMD),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            decoration: BoxDecoration(
              color: isSelected
                  ? AppColors.sidebarSelected
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(AppSizes.radiusMD),
              border: isSelected
                  ? const Border(
                      left: BorderSide(
                        color: AppColors.sidebarSelBorder, width: 3),
                    )
                  : null,
            ),
            child: Row(
              children: [
                Icon(
                  item.icon,
                  size: AppSizes.iconMD,
                  color: isSelected
                      ? AppColors.primary
                      : AppColors.textSecondary,
                ),
                const SizedBox(width: 10),
                Text(
                  item.label,
                  style: AppTextStyles.labelLarge.copyWith(
                    color: isSelected
                        ? AppColors.primary
                        : AppColors.textSecondary,
                    fontWeight:
                        isSelected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _UserFooter extends ConsumerWidget {
  final AuthState auth;
  const _UserFooter({required this.auth});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: AppColors.primaryLight,
            child: Text(
              (auth.userId?.isNotEmpty == true)
                  ? auth.userId![0].toUpperCase()
                  : '?',
              style: AppTextStyles.labelMedium.copyWith(
                color: AppColors.primary, fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  auth.userId ?? '',
                  style: AppTextStyles.labelLarge,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  auth.userRole ?? '',
                  style: AppTextStyles.caption,
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.logout_outlined,
                size: 18, color: AppColors.textMuted),
            tooltip: 'Sign out',
            onPressed: () async {
              await ref.read(authProvider.notifier).logout();
              if (context.mounted) context.go('/login');
            },
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
          ),
        ],
      ),
    );
  }
}
