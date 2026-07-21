// TypeScript mirrors of the Aegis backend response models.
// Keep these in sync with api/routers/*.py and src/aegis/core/master_agent.py.

export type UserRole = "admin" | "manager" | "employee";

export interface AuthToken {
  access_token: string;
  token_type: string;
  user_id: string;
  user_role: UserRole;
  expires_in: number;
}

export interface SourceChunk {
  text: string;
  source: string;
  department?: string;
  chunk_index: number;
}

export interface AccessDecision {
  permitted: boolean;
  user_role: string;
  user_id: string;
  query: string;
  permitted_departments: string[];
  denial_reason?: string | null;
}

export type Verdict = "high" | "medium" | "low";
export type RoutingPath =
  | "direct"
  | "disclaimer"
  | "web"
  | "refuse"
  | "denied"
  | "direct_llm";

export interface QueryResult {
  answer: string;
  confidence: number;
  verdict: Verdict;
  should_refuse: boolean;
  is_external: boolean;
  sources: SourceChunk[];
  chunks_used: number;
  routing_path: RoutingPath;
  access_decision: AccessDecision;
  model_used: string;
  latency_ms: number;
  web_used: boolean;
  cross_model_eval: boolean;
  reranker_used: boolean;
  db_triggered: boolean;
  columns_blocked: string[];
  columns_anonymized: string[];
  cached?: boolean;
  query_source?: string;
}

export interface DocumentInfo {
  doc_id: string;
  filename: string;
  project_id: string;
  chunks_count: number;
}

export interface UploadResult {
  doc_id: string;
  filename: string;
  chunks_created: number;
  status: string;
  message: string;
}

export interface ProjectInfo {
  project_id: string;
  project_name: string;
  collection_name: string;
}

export interface AuditRecord {
  id: number;
  timestamp: string;
  user_id: string;
  user_role: string;
  query_text: string;
  project_id?: string | null;
  departments_accessed?: string | null;
  access_verdict: string;
  denial_reason?: string | null;
  confidence_score?: number | null;
  confidence_verdict?: string | null;
  routing_path?: string | null;
  model_used?: string | null;
  latency_ms?: number | null;
  db_triggered?: number | null;
  rag_triggered?: number | null;
  firewall_applied?: number | null;
  raw_data_destroyed?: number | null;
  columns_blocked?: string | null;
  columns_anonymized?: string | null;
}

export interface HealthStatus {
  status: "ok" | "degraded" | "error";
  version: string;
  llm_provider: string;
  llm_model: string;
  embed_provider: string;
  db_connected: boolean;
  vector_store_ok: boolean;
  demo_mode: boolean;
  message: string;
}

export interface ModelInfo {
  id: string;
  name: string;
}

export interface AdminUser {
  user_id: string;
  role: string;
}

// RAG modes exposed in the UI (mirrors src/aegis/config.py RAG_MODES).
export const RAG_MODES: { id: string; label: string }[] = [
  { id: "general", label: "General / Mixed" },
  { id: "hr", label: "HR / Policy" },
  { id: "legal", label: "Legal" },
  { id: "financial", label: "Financial" },
  { id: "technical", label: "Technical" },
  { id: "medical", label: "Medical" },
  { id: "research", label: "Research" },
  { id: "compliance", label: "Compliance / Regulatory" },
  { id: "contracts", label: "Contracts" },
  { id: "operations", label: "Operations / SOPs" },
];
