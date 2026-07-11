import { api } from "./client";
import type {
  AdminUser,
  AuditRecord,
  AuthToken,
  DocumentInfo,
  HealthStatus,
  ModelInfo,
  ProjectInfo,
  QueryResult,
  UploadResult,
} from "./types";

// ── Auth ─────────────────────────────────────────────────────────────────────
export async function login(
  username: string,
  password: string,
): Promise<AuthToken> {
  const body = new URLSearchParams({ username, password });
  const { data } = await api.post<AuthToken>("/api/v1/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

// ── Query (non-streaming) ─────────────────────────────────────────────────────
export async function query(params: {
  userQuery: string;
  projectId: string;
  conversationId?: string;
}): Promise<QueryResult> {
  const { data } = await api.post<QueryResult>("/api/v1/query", {
    user_query: params.userQuery,
    project_id: params.projectId,
    conversation_id: params.conversationId,
  });
  return data;
}

// ── LLM models ────────────────────────────────────────────────────────────────
export async function listModels(
  provider: string,
  apiKey = "",
): Promise<ModelInfo[]> {
  const { data } = await api.get<{ models: ModelInfo[]; message?: string }>(
    "/api/v1/llm/models",
    { params: { provider, ...(apiKey ? { api_key: apiKey } : {}) } },
  );
  return data.models ?? [];
}

// ── Documents ─────────────────────────────────────────────────────────────────
export async function listDocuments(
  projectId: string,
): Promise<DocumentInfo[]> {
  const { data } = await api.get<DocumentInfo[]>("/api/v1/documents", {
    params: { project_id: projectId },
  });
  return data;
}

export async function uploadDocuments(params: {
  projectId: string;
  ragMode: string;
  files: File[];
  onProgress?: (fraction: number) => void;
}): Promise<UploadResult[]> {
  const form = new FormData();
  form.append("project_id", params.projectId);
  form.append("rag_mode", params.ragMode);
  for (const f of params.files) form.append("files", f, f.name);

  const { data } = await api.post<UploadResult[]>(
    "/api/v1/documents/upload",
    form,
    {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (params.onProgress && e.total) params.onProgress(e.loaded / e.total);
      },
    },
  );
  return data;
}

export async function deleteDocument(
  docId: string,
  projectId: string,
): Promise<void> {
  await api.delete(`/api/v1/documents/${encodeURIComponent(docId)}`, {
    params: { project_id: projectId },
  });
}

// ── Projects ──────────────────────────────────────────────────────────────────
export async function listProjects(): Promise<ProjectInfo[]> {
  const { data } = await api.get<ProjectInfo[]>("/api/v1/projects");
  return data;
}

export async function createProject(name: string): Promise<ProjectInfo> {
  const { data } = await api.post<ProjectInfo>("/api/v1/projects", { name });
  return data;
}

// ── Audit ─────────────────────────────────────────────────────────────────────
export async function getAuditLog(limit = 200): Promise<AuditRecord[]> {
  const { data } = await api.get<AuditRecord[]>("/api/v1/audit", {
    params: { limit },
  });
  return data;
}

export async function exportAuditCsv(): Promise<Blob> {
  const { data } = await api.post("/api/v1/audit/export", null, {
    responseType: "blob",
  });
  return data as Blob;
}

// ── Health ────────────────────────────────────────────────────────────────────
export async function getHealth(): Promise<HealthStatus> {
  const { data } = await api.get<HealthStatus>("/api/v1/health");
  return data;
}

// ── Admin ─────────────────────────────────────────────────────────────────────
export async function getAdminUsers(): Promise<AdminUser[]> {
  const { data } = await api.get<{ users: AdminUser[] }>("/api/v1/admin/users");
  return data.users ?? [];
}

export async function getAccessRules(): Promise<Record<string, unknown>> {
  const { data } = await api.get<{ rules: Record<string, unknown> }>(
    "/api/v1/admin/access-rules",
  );
  return data.rules ?? {};
}

export async function getConnectors(): Promise<Record<string, boolean>> {
  const { data } = await api.get<{ connectors: Record<string, boolean> }>(
    "/api/v1/admin/connectors",
  );
  return data.connectors ?? {};
}
