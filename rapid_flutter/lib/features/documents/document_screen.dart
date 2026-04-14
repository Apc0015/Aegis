import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../providers/auth_provider.dart';
import '../../providers/document_provider.dart';
import '../../providers/project_provider.dart';
import '../../shared/widgets/error_banner.dart';
import 'widgets/document_list_tile.dart';
import 'widgets/upload_drop_zone.dart';
import 'widgets/upload_progress_card.dart';

class DocumentScreen extends ConsumerStatefulWidget {
  const DocumentScreen({super.key});

  @override
  ConsumerState<DocumentScreen> createState() => _DocumentScreenState();
}

class _DocumentScreenState extends ConsumerState<DocumentScreen> {
  final List<UploadJob> _uploadJobs = [];

  Future<void> _handleFiles(List<PlatformFile> files) async {
    final activeProject = ref.read(activeProjectProvider);
    if (activeProject == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Select a project before uploading documents')),
      );
      return;
    }

    setState(() {
      for (final f in files) {
        _uploadJobs.add(UploadJob(
          filename: f.name,
          status: UploadStatus.uploading,
        ));
      }
    });

    for (int i = 0; i < files.length; i++) {
      final f = files[i];
      final jobIndex = _uploadJobs.length - files.length + i;
      try {
        final result = await ref
            .read(documentUploadProvider.notifier)
            .upload(f, activeProject.projectId);
        setState(() {
          _uploadJobs[jobIndex] = _uploadJobs[jobIndex].copyWith(
            status: UploadStatus.success,
            chunksCreated: result.chunksCreated,
          );
        });
        ref.invalidate(documentsProvider);
      } catch (e) {
        setState(() {
          _uploadJobs[jobIndex] = _uploadJobs[jobIndex].copyWith(
            status: UploadStatus.error,
            errorMessage: e.toString().replaceFirst('Exception: ', ''),
          );
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final docsAsync = ref.watch(documentsProvider);
    final authState = ref.watch(authProvider);
    final activeProject = ref.watch(activeProjectProvider);
    final canDelete = authState.userRole == 'admin' ||
        authState.userRole == 'manager';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSizes.paddingXL),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ────────────────────────────────────────────────────
            Row(
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Documents', style: AppTextStyles.displaySmall),
                    const SizedBox(height: 4),
                    Text(
                      activeProject != null
                          ? 'Project: ${activeProject.projectName}'
                          : 'Select a project to manage documents',
                      style: AppTextStyles.bodySmall,
                    ),
                  ],
                ),
              ],
            ).animate().fadeIn(duration: 200.ms),
            const SizedBox(height: 24),

            // ── Upload zone ──────────────────────────────────────────────
            if (activeProject != null) ...[
              UploadDropZone(
                projectId: activeProject.projectId,
                onFilesSelected: _handleFiles,
              ).animate().fadeIn(duration: 250.ms, delay: 50.ms),
              const SizedBox(height: 16),
            ],

            // ── Upload progress ──────────────────────────────────────────
            if (_uploadJobs.isNotEmpty) ...[
              UploadProgressCard(
                jobs: _uploadJobs,
                onDismiss: () => setState(() => _uploadJobs.clear()),
              ).animate().fadeIn(duration: 150.ms),
              const SizedBox(height: 16),
            ],

            // ── Document list ────────────────────────────────────────────
            Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(AppSizes.radiusLG),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.all(AppSizes.paddingLG),
                    child: Row(
                      children: [
                        const Icon(Icons.folder_open_outlined,
                            size: 16,
                            color: AppColors.textSecondary),
                        const SizedBox(width: 8),
                        Text('Indexed Documents',
                            style: AppTextStyles.headlineSmall),
                        const Spacer(),
                        docsAsync.when(
                          loading: () => const SizedBox.shrink(),
                          error: (_, __) => const SizedBox.shrink(),
                          data: (docs) => Text(
                            '${docs.length} file${docs.length != 1 ? 's' : ''}',
                            style: AppTextStyles.caption,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Divider(height: 1),
                  docsAsync.when(
                    loading: () => const Padding(
                      padding: EdgeInsets.all(AppSizes.paddingXL),
                      child: Center(
                          child:
                              CircularProgressIndicator(strokeWidth: 2)),
                    ),
                    error: (e, _) => Padding(
                      padding: const EdgeInsets.all(AppSizes.paddingMD),
                      child: ErrorBanner(message: e.toString()),
                    ),
                    data: (docs) {
                      if (docs.isEmpty) {
                        return Padding(
                          padding: const EdgeInsets.all(AppSizes.paddingXXL),
                          child: Center(
                            child: Column(
                              children: [
                                const Icon(Icons.inbox_outlined,
                                    size: 36,
                                    color: AppColors.textMuted),
                                const SizedBox(height: 12),
                                Text('No documents indexed yet',
                                    style: AppTextStyles.bodySmall),
                              ],
                            ),
                          ),
                        );
                      }
                      return ListView.separated(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: docs.length,
                        separatorBuilder: (_, __) =>
                            const Divider(height: 1),
                        itemBuilder: (_, i) => DocumentListTile(
                          document: docs[i],
                          canDelete: canDelete,
                          onDelete: canDelete
                              ? () => _confirmDelete(context, docs[i].docId,
                                  docs[i].filename)
                              : null,
                        ),
                      );
                    },
                  ),
                ],
              ),
            ).animate().fadeIn(duration: 250.ms, delay: 100.ms),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmDelete(
      BuildContext context, String docId, String filename) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete document?'),
        content: Text('Remove "$filename" from the index. This cannot be undone.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(
                foregroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final activeProject = ref.read(activeProjectProvider);
      await ref
          .read(documentUploadProvider.notifier)
          .delete(docId, activeProject?.projectId ?? '');
      ref.invalidate(documentsProvider);
    }
  }
}
