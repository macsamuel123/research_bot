import type { ApiClient } from "./client";
import {
  ApiError,
  isSchedule,
  type Finding,
  type Message,
  type ResearchDetail,
  type ResearchSummary,
  type Run,
  type Schedule,
  type WatchPatch,
} from "./types";

/**
 * Deterministic in-memory implementation of ApiClient for NEXT_PUBLIC_USE_MOCKS=1.
 * The store is rebuilt from the fixtures on every page load (module init), and
 * `createMockClient()` gives tests a fresh, isolated store.
 * The watch rules mirror the backend (M7-C2) so stage 2 only swaps the implementation.
 */

interface StoredResearch {
  id: number;
  title: string;
  topic: string;
  created_at: string;
  unread: boolean;
  watch_enabled: boolean;
  watch_enabled_at: string | null;
  schedule: Schedule | null;
  last_run_at: string | null;
  last_activity_at: string;
}

interface StoredFinding extends Finding {
  research_id: number;
  dismissed: boolean;
}

interface StoredRun extends Run {
  research_id: number;
}

interface StoredMessage extends Message {
  research_id: number;
}

interface Store {
  researches: StoredResearch[];
  messages: StoredMessage[];
  findings: StoredFinding[];
  runs: StoredRun[];
  nextId: number;
}

const T = (iso: string): string => new Date(iso).toISOString();

function fixtures(): Store {
  const researches: StoredResearch[] = [
    {
      id: 1,
      title: "EU AI Act enforcement",
      topic: "How is the EU AI Act being enforced in 2026?",
      created_at: T("2026-11-01T08:00:00Z"),
      unread: false,
      watch_enabled: true,
      watch_enabled_at: T("2026-11-01T08:05:00Z"),
      schedule: "daily",
      last_run_at: T("2026-11-10T08:00:00Z"),
      last_activity_at: T("2026-11-10T08:02:00Z"),
    },
    {
      id: 2,
      title: "Solid-state battery startups",
      topic: "Which solid-state battery startups shipped production cells?",
      created_at: T("2026-11-05T12:00:00Z"),
      unread: true,
      watch_enabled: false,
      watch_enabled_at: null,
      schedule: null,
      last_run_at: T("2026-11-09T18:00:00Z"),
      last_activity_at: T("2026-11-09T18:01:00Z"),
    },
    {
      id: 3,
      title: "Rust async runtimes",
      topic: "State of Rust async runtimes beyond tokio",
      created_at: T("2026-10-20T10:00:00Z"),
      unread: false,
      watch_enabled: false,
      watch_enabled_at: T("2026-10-21T10:00:00Z"),
      schedule: "weekly",
      last_run_at: null,
      last_activity_at: T("2026-10-20T10:00:00Z"),
    },
  ];

  const messages: StoredMessage[] = [
    { id: 1, research_id: 1, role: "user", content: researches[0]!.topic, created_at: T("2026-11-01T08:00:00Z") },
    {
      id: 2,
      research_id: 1,
      role: "assistant",
      content:
        "Enforcement is ramping up: the AI Office has opened its first formal inquiries and national market-surveillance authorities are publishing guidance. Findings are in the panel.",
      created_at: T("2026-11-01T08:01:00Z"),
    },
    { id: 3, research_id: 2, role: "user", content: researches[1]!.topic, created_at: T("2026-11-05T12:00:00Z") },
    {
      id: 4,
      research_id: 2,
      role: "assistant",
      content: "Two startups report pilot-line production; none has shipped automotive volume yet.",
      created_at: T("2026-11-09T18:01:00Z"),
    },
    { id: 5, research_id: 3, role: "user", content: researches[2]!.topic, created_at: T("2026-10-20T10:00:00Z") },
  ];

  const findings: StoredFinding[] = [
    {
      id: 101,
      research_id: 1,
      title: "AI Office opens first formal inquiry into a general-purpose model provider",
      url: "https://digital-strategy.example.eu/news/ai-office-first-inquiry",
      summary: "The AI Office requested technical documentation under the GPAI obligations, the first use of its information powers.",
      source: "digital-strategy.example.eu",
      found_at: T("2026-11-10T08:01:00Z"),
      dismissed: false,
    },
    {
      id: 102,
      research_id: 1,
      title: "Germany designates its market-surveillance authority for high-risk systems",
      url: "https://news.example.de/ai-act/marktueberwachung-benannt",
      summary: "The federal network agency will supervise high-risk AI systems, with a dedicated unit starting in Q1.",
      source: "news.example.de",
      found_at: T("2026-11-09T08:01:00Z"),
      dismissed: false,
    },
    {
      id: 103,
      research_id: 1,
      title: "Guidance on prohibited practices: what counts as manipulative AI",
      url: "https://law.example.com/blog/ai-act-prohibited-practices-guidance-explained-in-plain-language",
      summary: "A practitioner summary of the Commission guidelines, with examples of dark patterns that fall under Article 5.",
      source: "law.example.com",
      found_at: T("2026-11-05T08:01:00Z"),
      dismissed: false,
    },
    {
      id: 104,
      research_id: 1,
      title: "Fines so far: none issued, but first penalty frameworks adopted",
      url: "https://policy.example.org/ai-act-penalties-tracker",
      summary: "A tracker of member-state penalty laws shows 11 states have adopted frameworks; no fines have been issued yet.",
      source: "policy.example.org",
      found_at: T("2026-11-02T08:01:00Z"),
      dismissed: false,
    },
    {
      id: 105,
      research_id: 1,
      title: "Dismissed earlier: duplicate press release",
      url: "https://press.example.com/release",
      summary: "Already dismissed; never shown.",
      source: "press.example.com",
      found_at: T("2026-11-03T08:01:00Z"),
      dismissed: true,
    },
    {
      id: 201,
      research_id: 2,
      title: "Startup A opens pilot line for 1 GWh of solid-state cells",
      url: "https://energy.example.com/startup-a-pilot-line",
      summary: "The pilot line targets sample cells for two automotive partners next year.",
      source: "energy.example.com",
      found_at: T("2026-11-09T18:00:00Z"),
      dismissed: false,
    },
    {
      id: 202,
      research_id: 2,
      title: "Startup B delays its B-sample shipments",
      url: "https://batteries.example.net/startup-b-delay",
      summary: "Yield problems at the separator stage push B-samples back by two quarters.",
      source: "batteries.example.net",
      found_at: T("2026-11-08T18:00:00Z"),
      dismissed: false,
    },
  ];

  const runs: StoredRun[] = [
    {
      id: 15,
      research_id: 1,
      started_at: T("2026-11-10T09:00:00Z"),
      finished_at: null,
      status: "running",
      trigger: "chat",
      cost_cents: 0,
      new_findings: 0,
    },
    {
      id: 14,
      research_id: 1,
      started_at: T("2026-11-10T08:00:00Z"),
      finished_at: T("2026-11-10T08:02:00Z"),
      status: "ok",
      trigger: "watch",
      cost_cents: 1234,
      new_findings: 3,
    },
    {
      id: 13,
      research_id: 1,
      started_at: T("2026-11-09T08:00:00Z"),
      finished_at: T("2026-11-09T08:03:00Z"),
      status: "capped",
      trigger: "watch",
      cost_cents: 50,
      new_findings: 1,
    },
    {
      id: 12,
      research_id: 1,
      started_at: T("2026-11-08T08:00:00Z"),
      finished_at: T("2026-11-08T08:00:30Z"),
      status: "error",
      trigger: "watch",
      cost_cents: 5,
      new_findings: 0,
    },
    {
      id: 11,
      research_id: 1,
      started_at: T("2026-11-01T08:00:00Z"),
      finished_at: T("2026-11-01T08:01:00Z"),
      status: "ok",
      trigger: "chat",
      cost_cents: 0,
      new_findings: 0,
    },
    {
      id: 21,
      research_id: 2,
      started_at: T("2026-11-09T18:00:00Z"),
      finished_at: T("2026-11-09T18:01:00Z"),
      status: "ok",
      trigger: "telegram",
      cost_cents: 23,
      new_findings: 2,
    },
  ];

  return { researches, messages, findings, runs, nextId: 1000 };
}

function summary(r: StoredResearch): ResearchSummary {
  return {
    id: r.id,
    title: r.title,
    unread: r.unread,
    watch_enabled: r.watch_enabled,
    schedule: r.schedule,
    last_activity_at: r.last_activity_at,
  };
}

/** Newest first by an ISO timestamp, ties broken by id desc (matches the backend ORDER BY). */
function sortDesc<T extends { id: number }>(items: T[], key: (x: T) => string): T[] {
  return [...items].sort((a, b) => key(b).localeCompare(key(a)) || b.id - a.id);
}

export interface MockClientOptions {
  /** Source of "now" for watch_enabled_at and new rows (deterministic in tests). */
  now?: () => string;
}

export function createMockClient(options: MockClientOptions = {}): ApiClient {
  const store = fixtures();
  const now = options.now ?? (() => new Date().toISOString());

  const find = (id: number): StoredResearch => {
    const r = store.researches.find((x) => x.id === id);
    if (!r) throw new ApiError(404, "Research not found");
    return r;
  };

  return {
    async listResearches() {
      return sortDesc(store.researches, (x) => x.last_activity_at).map(summary);
    },

    async createResearch(topic) {
      const trimmed = topic.trim();
      if (!trimmed) throw new ApiError(422, "Topic must not be blank");
      const at = now();
      const id = store.nextId++;
      const r: StoredResearch = {
        id,
        title: trimmed.length > 80 ? `${trimmed.slice(0, 79)}…` : trimmed,
        topic: trimmed,
        created_at: at,
        unread: false,
        watch_enabled: false,
        watch_enabled_at: null,
        schedule: null,
        last_run_at: null,
        last_activity_at: at,
      };
      store.researches.push(r);
      store.messages.push({ id: store.nextId++, research_id: id, role: "user", content: trimmed, created_at: at });
      return summary(r);
    },

    async getResearch(id) {
      const r = find(id);
      const running = store.runs.find((x) => x.research_id === id && x.status === "running");
      const detail: ResearchDetail = {
        ...summary(r),
        topic: r.topic,
        created_at: r.created_at,
        last_run_at: r.last_run_at,
        watch_enabled_at: r.watch_enabled_at,
        messages: store.messages
          .filter((m) => m.research_id === id)
          .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id)
          .map(({ id: mid, role, content, created_at }) => ({ id: mid, role, content, created_at })),
        active_run: running
          ? { id: running.id, status: "running", trigger: running.trigger, started_at: running.started_at }
          : null,
      };
      return detail;
    },

    async markRead(id) {
      find(id).unread = false;
    },

    async updateWatch(id, patch: WatchPatch) {
      const r = find(id);
      if (patch.schedule !== undefined && !isSchedule(patch.schedule)) {
        throw new ApiError(422, "schedule must be one of 6h, daily, weekly");
      }
      if (patch.watch_enabled !== undefined && typeof patch.watch_enabled !== "boolean") {
        throw new ApiError(422, "watch_enabled must be a boolean");
      }
      const at = now();
      if (patch.schedule !== undefined && patch.schedule !== r.schedule) {
        r.schedule = patch.schedule;
        r.watch_enabled_at = at;
      }
      if (patch.watch_enabled === true) {
        if (r.schedule === null) r.schedule = "daily";
        if (!r.watch_enabled) r.watch_enabled_at = at;
        r.watch_enabled = true;
      } else if (patch.watch_enabled === false) {
        // Pause keeps the schedule.
        r.watch_enabled = false;
      }
      return summary(r);
    },

    async deleteResearch(id) {
      find(id);
      store.researches = store.researches.filter((x) => x.id !== id);
      store.messages = store.messages.filter((x) => x.research_id !== id);
      store.findings = store.findings.filter((x) => x.research_id !== id);
      store.runs = store.runs.filter((x) => x.research_id !== id);
    },

    async listFindings(researchId) {
      find(researchId);
      return sortDesc(
        store.findings.filter((f) => f.research_id === researchId && !f.dismissed),
        (x) => x.found_at,
      )
        .map(({ id, title, url, summary: s, source, found_at }) => ({
          id,
          title,
          url,
          summary: s,
          source,
          found_at,
        }));
    },

    async dismissFinding(findingId) {
      const f = store.findings.find((x) => x.id === findingId);
      if (!f) throw new ApiError(404, "Finding not found");
      f.dismissed = true;
    },

    async listRuns(researchId) {
      find(researchId);
      return sortDesc(
        store.runs.filter((x) => x.research_id === researchId),
        (x) => x.started_at,
      )
        .map(({ id, started_at, finished_at, status, trigger, cost_cents, new_findings }) => ({
          id,
          started_at,
          finished_at,
          status,
          trigger,
          cost_cents,
          new_findings,
        }));
    },
  };
}

let singleton: ApiClient | null = null;

/** One store per page load, shared by every component. */
export function getMockClient(): ApiClient {
  singleton ??= createMockClient();
  return singleton;
}
