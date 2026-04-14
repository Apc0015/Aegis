import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../data/models/document_models.dart';

class DocumentListTile extends StatelessWidget {
  final DocumentInfo document;
  final bool canDelete;
  final VoidCallback? onDelete;

  const DocumentListTile({
    super.key,
    required this.document,
    this.canDelete = false,
    this.onDelete,
  });

  String _ext(String filename) {
    final parts = filename.split('.');
    return parts.length > 1 ? parts.last.toUpperCase() : 'FILE';
  }

  Color _extColor(String ext) {
    switch (ext) {
      case 'PDF':
        return const Color(0xFFEF4444);
      case 'DOCX':
      case 'DOC':
        return const Color(0xFF3B82F6);
      case 'CSV':
        return const Color(0xFF10B981);
      default:
        return AppColors.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final ext = _ext(document.filename);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: _extColor(ext).withOpacity(0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Center(
              child: Text(ext.length > 3 ? ext.substring(0, 3) : ext,
                  style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                      color: _extColor(ext),
                      letterSpacing: 0.3)),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(document.filename,
                    style: AppTextStyles.bodySmall
                        .copyWith(color: AppColors.textPrimary),
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Text(
                  '${document.chunkCount} chunks · ${document.projectId}',
                  style: AppTextStyles.caption,
                ),
              ],
            ),
          ),
          if (canDelete && onDelete != null) ...[
            const SizedBox(width: 8),
            IconButton(
              onPressed: onDelete,
              icon: const Icon(Icons.delete_outline,
                  size: 16, color: AppColors.textMuted),
              padding: EdgeInsets.zero,
              constraints:
                  const BoxConstraints(minWidth: 28, minHeight: 28),
              tooltip: 'Delete document',
            ),
          ],
        ],
      ),
    );
  }
}
