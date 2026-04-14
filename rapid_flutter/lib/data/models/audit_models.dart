class AuditRecord {
  final int id;
  final String timestamp;
  final String userId;
  final String userRole;
  final String queryText;
  final String? projectId;
  final String? departmentsAccessed;
  final String accessVerdict;
  final String? denialReason;
  final double? confidenceScore;
  final String? confidenceVerdict;
  final String? routingPath;
  final String? modelUsed;
  final int? latencyMs;
  final int? dbTriggered;
  final int? ragTriggered;
  final int? firewallApplied;
  final int? rawDataDestroyed;
  final String? columnsBlocked;
  final String? columnsAnonymized;

  const AuditRecord({
    required this.id,
    required this.timestamp,
    required this.userId,
    required this.userRole,
    required this.queryText,
    this.projectId,
    this.departmentsAccessed,
    required this.accessVerdict,
    this.denialReason,
    this.confidenceScore,
    this.confidenceVerdict,
    this.routingPath,
    this.modelUsed,
    this.latencyMs,
    this.dbTriggered,
    this.ragTriggered,
    this.firewallApplied,
    this.rawDataDestroyed,
    this.columnsBlocked,
    this.columnsAnonymized,
  });

  // ── Convenience getters ───────────────────────────────────────────────────────
  String get query => queryText;
  String? get verdict => confidenceVerdict;
  double? get confidence => confidenceScore;
  String get projectIdOrEmpty => projectId ?? '';

  factory AuditRecord.fromJson(Map<String, dynamic> j) => AuditRecord(
    id: j['id'] as int? ?? 0,
    timestamp: j['timestamp'] as String? ?? '',
    userId: j['user_id'] as String? ?? '',
    userRole: j['user_role'] as String? ?? '',
    queryText: j['query_text'] as String? ?? '',
    projectId: j['project_id'] as String?,
    departmentsAccessed: j['departments_accessed'] as String?,
    accessVerdict: j['access_verdict'] as String? ?? '',
    denialReason: j['denial_reason'] as String?,
    confidenceScore: (j['confidence_score'] as num?)?.toDouble(),
    confidenceVerdict: j['confidence_verdict'] as String?,
    routingPath: j['routing_path'] as String?,
    modelUsed: j['model_used'] as String?,
    latencyMs: j['latency_ms'] as int?,
    dbTriggered: j['db_triggered'] as int?,
    ragTriggered: j['rag_triggered'] as int?,
    firewallApplied: j['firewall_applied'] as int?,
    rawDataDestroyed: j['raw_data_destroyed'] as int?,
    columnsBlocked: j['columns_blocked'] as String?,
    columnsAnonymized: j['columns_anonymized'] as String?,
  );
}
