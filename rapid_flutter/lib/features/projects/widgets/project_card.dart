import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../data/models/project_models.dart';

class ProjectCard extends StatelessWidget {
  final ProjectInfo project;
  final bool isActive;
  final VoidCallback onSelect;

  const ProjectCard({
    super.key,
    required this.project,
    required this.isActive,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onSelect,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.all(AppSizes.paddingLG),
        decoration: BoxDecoration(
          color: isActive ? AppColors.primaryLight : AppColors.surface,
          borderRadius: BorderRadius.circular(AppSizes.radiusLG),
          border: Border.all(
            color: isActive ? AppColors.primary : AppColors.border,
            width: isActive ? 1.5 : 1,
          ),
          boxShadow: isActive
              ? [
                  BoxShadow(
                    color: AppColors.primary.withOpacity(0.08),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ]
              : [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.03),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: isActive
                        ? AppColors.primary
                        : AppColors.surfaceVariant,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    Icons.folder_outlined,
                    size: 18,
                    color: isActive ? Colors.white : AppColors.textSecondary,
                  ),
                ),
                const Spacer(),
                if (isActive)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppColors.primary,
                      borderRadius: BorderRadius.circular(AppSizes.radiusFull),
                    ),
                    child: Text('Active',
                        style: AppTextStyles.labelSmall
                            .copyWith(color: Colors.white)),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              project.projectName,
              style: AppTextStyles.headlineSmall.copyWith(
                color:
                    isActive ? AppColors.primary : AppColors.textPrimary,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            Text(
              project.projectId,
              style: AppTextStyles.caption,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
