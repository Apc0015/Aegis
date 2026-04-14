import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/project_provider.dart';
import '../../shared/widgets/error_banner.dart';
import 'widgets/create_project_dialog.dart';
import 'widgets/project_card.dart';

class ProjectScreen extends ConsumerWidget {
  const ProjectScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final projectsAsync = ref.watch(projectsProvider);
    final activeProject = ref.watch(activeProjectProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSizes.paddingXL),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1000),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ────────────────────────────────────────────────────
            Row(
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Projects', style: AppTextStyles.displaySmall),
                    const SizedBox(height: 4),
                    Text('Manage document collections',
                        style: AppTextStyles.bodySmall),
                  ],
                ),
                const Spacer(),
                ElevatedButton.icon(
                  onPressed: () => _showCreateDialog(context, ref),
                  icon: const Icon(Icons.add, size: 16),
                  label: const Text('New Project'),
                ),
              ],
            ).animate().fadeIn(duration: 200.ms),
            const SizedBox(height: 28),

            // ── Grid ─────────────────────────────────────────────────────
            projectsAsync.when(
              loading: () => const Center(
                  child: CircularProgressIndicator(strokeWidth: 2)),
              error: (e, _) =>
                  ErrorBanner(message: e.toString()),
              data: (projects) {
                if (projects.isEmpty) {
                  return Center(
                    child: Column(
                      children: [
                        const SizedBox(height: 60),
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            color: AppColors.surfaceVariant,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.folder_open_outlined,
                              size: 36, color: AppColors.textMuted),
                        ),
                        const SizedBox(height: 16),
                        Text('No projects yet',
                            style: AppTextStyles.headlineMedium),
                        const SizedBox(height: 6),
                        Text(
                          'Create your first project to start indexing documents',
                          style: AppTextStyles.bodySmall,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 24),
                        ElevatedButton.icon(
                          onPressed: () => _showCreateDialog(context, ref),
                          icon: const Icon(Icons.add, size: 16),
                          label: const Text('Create Project'),
                        ),
                      ],
                    ),
                  );
                }

                return LayoutBuilder(
                  builder: (context, constraints) {
                    final crossAxisCount =
                        constraints.maxWidth > AppSizes.breakpointTablet
                            ? 3
                            : 2;
                    return GridView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: crossAxisCount,
                        crossAxisSpacing: 14,
                        mainAxisSpacing: 14,
                        childAspectRatio: 1.6,
                      ),
                      itemCount: projects.length,
                      itemBuilder: (_, i) => ProjectCard(
                        project: projects[i],
                        isActive:
                            activeProject?.projectId == projects[i].projectId,
                        onSelect: () {
                          ref
                              .read(activeProjectProvider.notifier)
                              .setActive(projects[i]);
                          context.go('/chat/${projects[i].projectId}');
                        },
                      ).animate().fadeIn(
                            duration: 200.ms,
                            delay: Duration(milliseconds: 40 * i),
                          ),
                    );
                  },
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showCreateDialog(
      BuildContext context, WidgetRef ref) async {
    final name = await showDialog<String>(
      context: context,
      builder: (_) => const CreateProjectDialog(),
    );
    if (name != null && name.isNotEmpty) {
      await ref.read(projectsProvider.notifier).createProject(name);
    }
  }
}
