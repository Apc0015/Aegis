class SourceChunk {
  final String text;
  final String source;
  final int chunkIndex;

  const SourceChunk({
    required this.text,
    required this.source,
    required this.chunkIndex,
  });

  factory SourceChunk.fromJson(Map<String, dynamic> j) => SourceChunk(
    text: j['text'] as String? ?? '',
    source: j['source'] as String? ?? 'Unknown',
    chunkIndex: j['chunk_index'] as int? ?? 0,
  );
}

class AccessDecision {
  final bool permitted;
  final String userRole;
  final String userId;
  final String query;
  final List<String> permittedDepartments;
  final String? denialReason;

  const AccessDecision({
    required this.permitted,
    required this.userRole,
    required this.userId,
    required this.query,
    required this.permittedDepartments,
    this.denialReason,
  });

  factory AccessDecision.fromJson(Map<String, dynamic> j) => AccessDecision(
    permitted: j['permitted'] as bool? ?? false,
    userRole: j['user_role'] as String? ?? '',
    userId: j['user_id'] as String? ?? '',
    query: j['query'] as String? ?? '',
    permittedDepartments: (j['permitted_departments'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList(),
    denialReason: j['denial_reason'] as String?,
  );
}

/// Mirrors the Python QueryResult dataclass exactly.
class QueryResult {
  final String answer;
  final double confidence;
  final String verdict;        // "high" | "medium" | "low"
  final bool shouldRefuse;
  final bool isExternal;
  final List<SourceChunk> sources;
  final int chunksUsed;
  final String routingPath;    // "direct" | "disclaimer" | "web" | "refuse" | "denied"
  final AccessDecision accessDecision;
  final String modelUsed;
  final int latencyMs;
  final bool webUsed;
  final bool crossModelEval;
  final bool rerankerUsed;
  final bool dbTriggered;
  final List<String> columnsBlocked;
  final List<String> columnsAnonymized;

  const QueryResult({
    required this.answer,
    required this.confidence,
    required this.verdict,
    required this.shouldRefuse,
    required this.isExternal,
    required this.sources,
    required this.chunksUsed,
    required this.routingPath,
    required this.accessDecision,
    required this.modelUsed,
    required this.latencyMs,
    required this.webUsed,
    required this.crossModelEval,
    required this.rerankerUsed,
    required this.dbTriggered,
    required this.columnsBlocked,
    required this.columnsAnonymized,
  });

  factory QueryResult.fromJson(Map<String, dynamic> j) => QueryResult(
    answer: j['answer'] as String? ?? '',
    confidence: (j['confidence'] as num? ?? 0.0).toDouble(),
    verdict: j['verdict'] as String? ?? 'low',
    shouldRefuse: j['should_refuse'] as bool? ?? false,
    isExternal: j['is_external'] as bool? ?? false,
    sources: (j['sources'] as List<dynamic>? ?? [])
        .map((s) => SourceChunk.fromJson(s as Map<String, dynamic>))
        .toList(),
    chunksUsed: j['chunks_used'] as int? ?? 0,
    routingPath: j['routing_path'] as String? ?? 'direct',
    accessDecision: AccessDecision.fromJson(
        j['access_decision'] as Map<String, dynamic>? ?? {}),
    modelUsed: j['model_used'] as String? ?? '',
    latencyMs: j['latency_ms'] as int? ?? 0,
    webUsed: j['web_used'] as bool? ?? false,
    crossModelEval: j['cross_model_eval'] as bool? ?? false,
    rerankerUsed: j['reranker_used'] as bool? ?? false,
    dbTriggered: j['db_triggered'] as bool? ?? false,
    columnsBlocked: (j['columns_blocked'] as List<dynamic>? ?? [])
        .map((e) => e.toString()).toList(),
    columnsAnonymized: (j['columns_anonymized'] as List<dynamic>? ?? [])
        .map((e) => e.toString()).toList(),
  );
}

/// A message in the chat history.
class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;           // live-updating text during streaming
  final QueryResult? result;      // non-null when assistant message is complete
  final DateTime timestamp;
  final bool isPartial;           // true while streaming

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.result,
    this.isPartial = false,
  });

  ChatMessage copyWith({
    String? content,
    QueryResult? result,
    bool? isPartial,
  }) =>
      ChatMessage(
        id: id,
        role: role,
        content: content ?? this.content,
        timestamp: timestamp,
        result: result ?? this.result,
        isPartial: isPartial ?? this.isPartial,
      );
}

enum MessageRole { user, assistant }
