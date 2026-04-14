import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

enum UploadStatus { uploading, success, error }

class UploadJob {
  final String filename;
  final UploadStatus status;
  final String? errorMessage;
  final int? chunksCreated;

  const UploadJob({
    required this.filename,
    required this.status,
    this.errorMessage,
    this.chunksCreated,
  });

  UploadJob copyWith({
    UploadStatus? status,
    String? errorMessage,
    int? chunksCreated,
  }) =>
      UploadJob(
        filename: filename,
        status: status ?? this.status,
        errorMessage: errorMessage ?? this.errorMessage,
        chunksCreated: chunksCreated ?? this.chunksCreated,
      );
}

class UploadProgressCard extends StatelessWidget {
  final List<UploadJob> jobs;
  final VoidCallback onDismiss;

  const UploadProgressCard({
    super.key,
    required this.jobs,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    if (jobs.isEmpty) return const SizedBox.shrink();

    final allDone = jobs.every((j) => j.status != UploadStatus.uploading);

    return Container(
      padding: const EdgeInsets.all(AppSizes.paddingMD),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSizes.radiusLG),
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
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
              Text('Uploading ${jobs.length} file${jobs.length > 1 ? 's' : ''}',
                  style: AppTextStyles.headlineSmall),
              const Spacer(),
              if (allDone)
                IconButton(
                  onPressed: onDismiss,
                  icon: const Icon(Icons.close, size: 16),
                  padding: EdgeInsets.zero,
                  constraints:
                      const BoxConstraints(minWidth: 24, minHeight: 24),
                ),
            ],
          ),
          const SizedBox(height: 10),
          ...jobs.map((job) => _JobRow(job: job)),
        ],
      ),
    );
  }
}

class _JobRow extends StatelessWidget {
  final UploadJob job;
  const _JobRow({required this.job});

  @override
  Widget build(BuildContext context) {
    Widget trailing;
    switch (job.status) {
      case UploadStatus.uploading:
        trailing = const SizedBox(
          width: 14,
          height: 14,
          child: CircularProgressIndicator(strokeWidth: 2),
        );
        break;
      case UploadStatus.success:
        trailing = Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle_outline,
                size: 14, color: AppColors.highConf),
            if (job.chunksCreated != null) ...[
              const SizedBox(width: 4),
              Text('${job.chunksCreated} chunks',
                  style: AppTextStyles.caption
                      .copyWith(color: AppColors.textSecondary)),
            ]
          ],
        );
        break;
      case UploadStatus.error:
        trailing = const Icon(Icons.error_outline,
            size: 14, color: AppColors.error);
        break;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          const Icon(Icons.insert_drive_file_outlined,
              size: 14, color: AppColors.textMuted),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  job.filename,
                  style: AppTextStyles.bodySmall,
                  overflow: TextOverflow.ellipsis,
                ),
                if (job.status == UploadStatus.error &&
                    job.errorMessage != null)
                  Text(job.errorMessage!,
                      style: AppTextStyles.caption
                          .copyWith(color: AppColors.error)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          trailing,
        ],
      ),
    );
  }
}
