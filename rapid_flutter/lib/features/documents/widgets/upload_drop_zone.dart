import 'package:desktop_drop/desktop_drop.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

class UploadDropZone extends StatefulWidget {
  final String projectId;
  final void Function(List<PlatformFile> files) onFilesSelected;

  const UploadDropZone({
    super.key,
    required this.projectId,
    required this.onFilesSelected,
  });

  @override
  State<UploadDropZone> createState() => _UploadDropZoneState();
}

class _UploadDropZoneState extends State<UploadDropZone> {
  bool _dragging = false;

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['pdf', 'txt', 'docx', 'md', 'csv'],
      withData: true,
    );
    if (result != null && result.files.isNotEmpty) {
      widget.onFilesSelected(result.files);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DropTarget(
      onDragDone: (detail) {
        setState(() => _dragging = false);
        // Convert XFile list to PlatformFile equivalent — use FilePicker on desktop
        // On web, DropTarget gives XFile; we wrap them
        final files = detail.files
            .map((xf) => PlatformFile(
                  name: xf.name,
                  path: xf.path,
                  size: 0, // unknown until read
                ))
            .toList();
        widget.onFilesSelected(files);
      },
      onDragEntered: (_) => setState(() => _dragging = true),
      onDragExited: (_) => setState(() => _dragging = false),
      child: GestureDetector(
        onTap: _pickFiles,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
          decoration: BoxDecoration(
            color: _dragging
                ? AppColors.primaryLight
                : AppColors.surfaceVariant,
            borderRadius: BorderRadius.circular(AppSizes.radiusLG),
            border: Border.all(
              color: _dragging ? AppColors.primary : AppColors.border,
              width: _dragging ? 2 : 1,
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.cloud_upload_outlined,
                size: 36,
                color: _dragging ? AppColors.primary : AppColors.textMuted,
              ),
              const SizedBox(height: 12),
              Text(
                _dragging ? 'Drop files here' : 'Drag & drop files here',
                style: AppTextStyles.headlineSmall.copyWith(
                  color: _dragging ? AppColors.primary : AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'or click to browse — PDF, TXT, DOCX, MD, CSV',
                style: AppTextStyles.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
