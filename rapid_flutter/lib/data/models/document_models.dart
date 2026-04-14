class DocumentInfo {
  final String docId;
  final String filename;
  final String projectId;
  final int chunkCount;

  const DocumentInfo({
    required this.docId,
    required this.filename,
    required this.projectId,
    required this.chunkCount,
  });

  factory DocumentInfo.fromJson(Map<String, dynamic> j) => DocumentInfo(
    docId: j['doc_id'] as String,
    filename: j['filename'] as String,
    projectId: j['project_id'] as String,
    chunkCount: (j['chunks_count'] ?? j['chunk_count']) as int? ?? 0,
  );
}

class UploadResult {
  final String docId;
  final String filename;
  final int chunksCreated;
  final String message;

  const UploadResult({
    required this.docId,
    required this.filename,
    required this.chunksCreated,
    required this.message,
  });

  factory UploadResult.fromJson(Map<String, dynamic> j) => UploadResult(
    docId: j['doc_id'] as String,
    filename: j['filename'] as String,
    chunksCreated: j['chunks_created'] as int? ?? 0,
    message: j['message'] as String? ?? '',
  );
}

/// Tracks per-file upload progress in the UI.
class UploadProgress {
  final String filename;
  final double progress; // 0.0 – 1.0
  final UploadStatus status;
  final String? error;

  const UploadProgress({
    required this.filename,
    required this.progress,
    required this.status,
    this.error,
  });

  UploadProgress copyWith({double? progress, UploadStatus? status, String? error}) =>
      UploadProgress(
        filename: filename,
        progress: progress ?? this.progress,
        status: status ?? this.status,
        error: error ?? this.error,
      );
}

enum UploadStatus { pending, uploading, done, failed }
