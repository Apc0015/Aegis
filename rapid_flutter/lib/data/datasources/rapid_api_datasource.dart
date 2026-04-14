import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import '../models/auth_models.dart';
import '../models/query_models.dart';
import '../models/document_models.dart';
import '../models/project_models.dart';
import '../models/audit_models.dart';
import '../models/health_models.dart';
import '../../core/network/sse_client.dart';

class RapidApiDataSource {
  final Dio _dio;
  late final SseClient _sse;

  RapidApiDataSource(this._dio) {
    _sse = SseClient(_dio);
  }

  // ── Auth ─────────────────────────────────────────────────────────────────────
  Future<AuthToken> login(String username, String password) async {
    final resp = await _dio.post(
      '/api/v1/auth/login',
      data: 'username=${Uri.encodeComponent(username)}&password=${Uri.encodeComponent(password)}',
      options: Options(contentType: 'application/x-www-form-urlencoded'),
    );
    return AuthToken.fromJson(resp.data as Map<String, dynamic>);
  }

  // ── Query ─────────────────────────────────────────────────────────────────────
  Future<QueryResult> query({
    required String userQuery,
    required String projectId,
    required String ragMode,
    bool forceDb = false,
    bool llmIntent = false,
  }) async {
    final resp = await _dio.post('/api/v1/query', data: {
      'user_query': userQuery,
      'project_id': projectId,
      'rag_mode': ragMode,
      'force_db': forceDb,
      'llm_intent': llmIntent,
    });
    return QueryResult.fromJson(resp.data as Map<String, dynamic>);
  }

  Stream<SseEvent> queryStream({
    required String userQuery,
    required String projectId,
    required String ragMode,
    String mode = 'auto',
    bool forceDb = false,
    bool llmIntent = false,
  }) =>
      _sse.stream(
        userQuery: userQuery,
        projectId: projectId,
        ragMode: ragMode,
        mode: mode,
        forceDb: forceDb,
        llmIntent: llmIntent,
      );

  /// Fetch available models for the given provider.
  /// For openrouter, pass the API key. For ollama, apiKey can be empty.
  Future<List<Map<String, String>>> listModels({
    required String provider,
    String apiKey = '',
  }) async {
    final resp = await _dio.get(
      '/api/v1/llm/models',
      queryParameters: {
        'provider': provider,
        if (apiKey.isNotEmpty) 'api_key': apiKey,
      },
    );
    final data = resp.data as Map<String, dynamic>;
    final models = data['models'] as List<dynamic>;
    return models
        .map((m) => {
              'id': m['id'] as String,
              'name': m['name'] as String,
            })
        .toList();
  }

  // ── Documents ────────────────────────────────────────────────────────────────
  Future<List<DocumentInfo>> listDocuments(String projectId) async {
    final resp = await _dio.get('/api/v1/documents',
        queryParameters: {'project_id': projectId});
    return (resp.data as List<dynamic>)
        .map((e) => DocumentInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<UploadResult>> uploadDocuments({
    required String projectId,
    required String ragMode,
    required List<({String name, List<int> bytes})> files,
    void Function(String filename, double progress)? onProgress,
  }) async {
    final formData = FormData();
    formData.fields.addAll([
      MapEntry('project_id', projectId),
      MapEntry('rag_mode', ragMode),
    ]);
    for (final f in files) {
      formData.files.add(MapEntry(
        'files',
        MultipartFile.fromBytes(f.bytes, filename: f.name),
      ));
    }
    final resp = await _dio.post(
      '/api/v1/documents/upload',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
      onSendProgress: (sent, total) {
        if (total > 0 && onProgress != null) {
          // Aggregate progress across all files
          onProgress('upload', sent / total);
        }
      },
    );
    return (resp.data as List<dynamic>)
        .map((e) => UploadResult.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Upload a single PlatformFile to the given project.
  Future<UploadResult> uploadDocument(
      PlatformFile file, String projectId) async {
    final bytes = file.bytes;
    if (bytes == null) throw Exception('File bytes unavailable: ${file.name}');
    final formData = FormData.fromMap({
      'project_id': projectId,
      'files': MultipartFile.fromBytes(bytes, filename: file.name),
    });
    final resp = await _dio.post(
      '/api/v1/documents/upload',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    // API returns a list; take first result
    final list = resp.data as List<dynamic>;
    return UploadResult.fromJson(list.first as Map<String, dynamic>);
  }

  Future<void> deleteDocument(String docId, String projectId) async {
    await _dio.delete('/api/v1/documents/$docId',
        queryParameters: {'project_id': projectId});
  }

  // ── Projects ─────────────────────────────────────────────────────────────────
  Future<List<ProjectInfo>> listProjects() async {
    final resp = await _dio.get('/api/v1/projects');
    return (resp.data as List<dynamic>)
        .map((e) => ProjectInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<ProjectInfo> createProject(String name) async {
    final resp = await _dio.post('/api/v1/projects', data: {'name': name});
    return ProjectInfo.fromJson(resp.data as Map<String, dynamic>);
  }

  // ── Audit ─────────────────────────────────────────────────────────────────────
  Future<List<AuditRecord>> getAuditLog({int limit = 200}) async {
    final resp = await _dio.get('/api/v1/audit',
        queryParameters: {'limit': limit});
    return (resp.data as List<dynamic>)
        .map((e) => AuditRecord.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<int>> exportAuditCsv() async {
    final resp = await _dio.post<List<int>>(
      '/api/v1/audit/export',
      options: Options(responseType: ResponseType.bytes),
    );
    return resp.data ?? [];
  }

  // ── Health ────────────────────────────────────────────────────────────────────
  Future<HealthStatus> getHealth() async {
    final resp = await _dio.get('/api/v1/health');
    return HealthStatus.fromJson(resp.data as Map<String, dynamic>);
  }
}
