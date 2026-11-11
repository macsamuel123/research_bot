export const SCHEDULES = ["6h", "daily", "weekly"] as const;
export type Schedule = (typeof SCHEDULES)[number];

export const RUN_STATUSES = ["running", "ok", "capped", "error"] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

export type RunTrigger = "chat" | "watch" | "telegram" | "api" | "digest";

export function isSchedule(value: unknown): value is Schedule {
  return typeof value === "string" && (SCHEDULES as readonly string[]).includes(value);
}

/** Sidebar item shape. Also returned by PATCH /api/researches/{id}. */
export interface ResearchSummary {
  id: number;
  title: string;
  unread: boolean;
  watch_enabled: boolean;
  schedule: Schedule | null;
  last_activity_at: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

/** Exactly the keys of `active_run` in GET /api/researches/{id} (M9-C5). */
export interface ActiveRun {
  id: number;
  trigger: RunTrigger;
  started_at: string;
}

export interface ResearchDetail extends ResearchSummary {
  topic: string;
  created_at: string;
  last_run_at: string | null;
  watch_enabled_at: string | null;
  messages: Message[];
  active_run: ActiveRun | null;
}

export interface Finding {
  id: number;
  title: string;
  url: string;
  summary: string;
  source: string;
  found_at: string;
}

export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  trigger: RunTrigger;
  /** Integer cents (INV-1). */
  cost_cents: number;
  new_findings: number;
}

/** One SSE event from POST /messages or /respond. */
export type RunEvent =
  | { type: "token"; text: string }
  | { type: "finding"; finding: Finding }
  | {
      type: "done";
      run_id: number;
      status: Exclude<RunStatus, "running">;
      /** Integer cents (INV-1). */
      cost_cents: number;
      new_findings: number;
    }
  | { type: "error"; message: string };

export interface RunStreamHandlers {
  /** Called once the server accepted the request (2xx), before any event. */
  onOpen?(): void;
  onEvent(event: RunEvent): void;
}

export interface WatchPatch {
  watch_enabled?: boolean;
  schedule?: Schedule;
}

/** Typed error for every non-2xx outcome, in both the mock and the http client. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}
