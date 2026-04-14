class HealthStatus {
  final String status;   // "ok" | "degraded" | "error"
  final String version;
  final String llmProvider;
  final String llmModel;
  final String embedProvider;
  final bool dbConnected;
  final bool vectorStoreOk;
  final String message;

  const HealthStatus({
    required this.status,
    required this.version,
    required this.llmProvider,
    required this.llmModel,
    required this.embedProvider,
    required this.dbConnected,
    required this.vectorStoreOk,
    required this.message,
  });

  factory HealthStatus.fromJson(Map<String, dynamic> j) => HealthStatus(
    status: j['status'] as String? ?? 'error',
    version: j['version'] as String? ?? '?',
    llmProvider: j['llm_provider'] as String? ?? '',
    llmModel: j['llm_model'] as String? ?? '',
    embedProvider: j['embed_provider'] as String? ?? '',
    dbConnected: j['db_connected'] as bool? ?? false,
    vectorStoreOk: j['vector_store_ok'] as bool? ?? false,
    message: j['message'] as String? ?? '',
  );

  bool get isOk => status == 'ok';
}
