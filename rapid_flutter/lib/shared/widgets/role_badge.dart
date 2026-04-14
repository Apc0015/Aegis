import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';

class RoleBadge extends StatelessWidget {
  final String role;
  const RoleBadge({super.key, required this.role});

  @override
  Widget build(BuildContext context) {
    final (Color text, Color bg, IconData icon) = switch (role) {
      'admin'    => (AppColors.roleAdmin,    AppColors.roleAdminBg,    Icons.shield_outlined),
      'manager'  => (AppColors.roleManager,  AppColors.roleManagerBg,  Icons.manage_accounts_outlined),
      _          => (AppColors.roleEmployee, AppColors.roleEmployeeBg, Icons.person_outline_rounded),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSizes.radiusFull),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: text),
          const SizedBox(width: 4),
          Text(
            role[0].toUpperCase() + role.substring(1),
            style: AppTextStyles.labelSmall.copyWith(color: text, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
