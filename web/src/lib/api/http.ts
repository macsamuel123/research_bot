import type { ApiClient } from "./client";
import {
  ApiError,
  type Finding,
  type ResearchDetail,
  type ResearchSummary,
  type Run,
  type RunStreamHandlers,
  type WatchPatch,
} from "./types";
import { readRunEvents } from "./sse";

async function errorFrom(response: Response): Promise<ApiError> {
  let detail = response.statusText || "Request failed";
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      detail = body.detail;
    }
  } catch {
    // Non-JSON error body: keep the status text.
  }
  return new ApiError(response.status, detail);
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
  });
  if (!response.ok) throw await errorFrom(response);
  return response;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await request(path, init);
  return (await response.json()) as T;
}

/** POSTs and pipes the SSE body to the handlers; non-2xx rejects before `onOpen`. */
async function stream(
  path: string,
  body: unknown,
  handlers: RunStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "text/event-stream",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!response.ok) throw await errorFrom(response);
  handlers.onOpen?.();
  if (!response.body) return;
  await readRunEvents(response.body, (e) => handlers.onEvent(e));
}

/** Same-origin client; the Next rewrite proxies /api to FastAPI. */
export function createHttpClient(): ApiClient {
  return {
    listResearches: () => json<ResearchSummary[]>("/api/researches"),
    createResearch: (topic) =>
      json<ResearchSummary>("/api/researches", { method: "POST", body: JSON.stringify({ topic }) }),
    getResearch: (id) => json<ResearchDetail>(`/api/researches/${id}`),
    markRead: async (id) => {
      await request(`/api/researches/${id}/read`, { method: "POST" });
    },
    updateWatch: (id, patch: WatchPatch) =>
      json<ResearchSummary>(`/api/researches/${id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
    deleteResearch: async (id) => {
      await request(`/api/researches/${id}`, { method: "DELETE" });
    },
    listFindings: (researchId) => json<Finding[]>(`/api/researches/${researchId}/findings`),
    dismissFinding: async (findingId) => {
      await request(`/api/findings/${findingId}/dismiss`, { method: "POST" });
    },
    listRuns: (researchId) => json<Run[]>(`/api/researches/${researchId}/runs`),
    sendMessage: (researchId, content, handlers, signal) =>
      stream(`/api/researches/${researchId}/messages`, { content }, handlers, signal),
    respond: (researchId, handlers, signal) =>
      stream(`/api/researches/${researchId}/respond`, undefined, handlers, signal),
  };
}
