import { API_BASE, getStoredToken } from "./client";
import type { QueryResult } from "./types";

// The Aegis stream endpoint (GET /api/v1/query/stream) is authenticated with a
// Bearer token, which the native EventSource API cannot send. We use fetch()
// with a ReadableStream reader instead so we can attach the Authorization header.

export type SseEvent =
  | { kind: "token"; token: string }
  | { kind: "result"; data: QueryResult }
  | { kind: "error"; message: string }
  | { kind: "done" };

export interface StreamParams {
  userQuery: string;
  projectId: string;
  ragMode: string;
  conversationId?: string;
  signal?: AbortSignal;
}

export async function* streamQuery(
  params: StreamParams,
): AsyncGenerator<SseEvent> {
  const qs = new URLSearchParams({
    user_query: params.userQuery,
    project_id: params.projectId,
    rag_mode: params.ragMode,
  });
  if (params.conversationId) qs.set("conversation_id", params.conversationId);

  const token = getStoredToken();
  const resp = await fetch(`${API_BASE}/api/v1/query/stream?${qs.toString()}`, {
    method: "GET",
    headers: {
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    signal: params.signal,
  });

  if (!resp.ok || !resp.body) {
    yield {
      kind: "error",
      message: `Stream failed (${resp.status} ${resp.statusText})`,
    };
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by newlines; each data line starts with "data: ".
      let idx: number;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        if (!line.startsWith("data: ")) continue;

        const payload = line.slice(6);
        if (payload === "[DONE]") {
          yield { kind: "done" };
          return;
        }

        // JSON payloads are either the final QueryResult or an {error} object.
        try {
          const json = JSON.parse(payload);
          if (json && typeof json === "object" && "error" in json) {
            yield { kind: "error", message: String(json.error) };
          } else {
            yield { kind: "result", data: json as QueryResult };
          }
        } catch {
          // Plain token — un-escape the SSE newline encoding.
          const tok = payload.replace(/\\n/g, "\n");
          if (tok.length > 0) yield { kind: "token", token: tok };
        }
      }
    }
    yield { kind: "done" };
  } finally {
    reader.releaseLock();
  }
}
