import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/models/document_models.dart';
import 'api_provider.dart';
import 'project_provider.dart';

/// All documents for the active project (or all projects if none selected).
final documentsProvider = FutureProvider<List<DocumentInfo>>((ref) async {
  final active = ref.watch(activeProjectProvider);
  final api = ref.watch(apiDataSourceProvider);
  return api.listDocuments(active?.projectId ?? '');
});

// ── Upload/delete notifier ───────────────────────────────────────────────────
class DocumentUploadNotifier extends StateNotifier<AsyncValue<void>> {
  final Ref _ref;
  DocumentUploadNotifier(this._ref) : super(const AsyncData(null));

  Future<UploadResult> upload(PlatformFile file, String projectId) async {
    final api = _ref.read(apiDataSourceProvider);
    return api.uploadDocument(file, projectId);
  }

  Future<void> delete(String docId, String projectId) async {
    final api = _ref.read(apiDataSourceProvider);
    await api.deleteDocument(docId, projectId);
  }
}

final documentUploadProvider =
    StateNotifierProvider<DocumentUploadNotifier, AsyncValue<void>>(
        (ref) => DocumentUploadNotifier(ref));
