import type { ApiClient } from "./client";
import {
  ApiError,
  isSchedule,
  type Finding,
  type Message,
  type ResearchDetail,
  type ResearchSummary,
  type Run,
  type RunEvent,
  type RunStreamHandlers,
  type Schedule,
  type WatchPatch,
} from "./types";

/** Same text as the backend's Conflict for a second send while a run is active (M9-C4). */
export const RUN_IN_PROGRESS = "a run is already in progress";
export const NO_PENDING_MESSAGE = "no pending user message";
export const MESSAGE_MAX_CHARS = 2000;

/** Fixture A: a chat run in progress that finishes after a few polls. */
export const FIXTURE_ACTIVE_RUN_ID = 4;
/** Fixture B: a watch run starts right after the thread is first opened, so a send gets 409. */
export const FIXTURE_CONFLICT_ID = 5;

/** The simulated assistant reply, streamed chunk by chunk. */
export const MOCK_REPLY_CHUNKS = [
  "Looking into this ",
  "now. ",
  "I searched recent sources ",
  "and compared what they report. ",
  "The most relevant result ",
  "is saved in the Findings panel ",
  "with its source link. ",
  "Research complete.",
] as const;

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

/** A run that the mock settles after a number of (deduplicated) getResearch calls. */
interface ScriptedRun {
  researchId: number;
  runId: number;
  /** getResearch calls still answered with the run active. */
  pollsLeft: number;
  reply: string;
  finding: Omit<StoredFinding, "id" | "research_id" | "found_at" | "dismissed">;
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
    {
      id: FIXTURE_ACTIVE_RUN_ID,
      title: "Quantum error correction milestones",
      topic: "Which quantum error correction milestones were reached this year?",
      created_at: T("2026-11-10T09:30:00Z"),
      unread: false,
      watch_enabled: false,
      watch_enabled_at: null,
      schedule: null,
      last_run_at: T("2026-11-10T09:30:00Z"),
      last_activity_at: T("2026-11-10T09:30:00Z"),
    },
    {
      id: FIXTURE_CONFLICT_ID,
      title: "Heat pump subsidies",
      topic: "Which countries changed heat pump subsidies this quarter?",
      created_at: T("2026-11-02T07:00:00Z"),
      unread: false,
      watch_enabled: true,
      watch_enabled_at: T("2026-11-02T07:05:00Z"),
      schedule: "6h",
      last_run_at: T("2026-11-10T06:00:00Z"),
      last_activity_at: T("2026-11-10T06:01:00Z"),
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
    { id: 6, research_id: 4, role: "user", content: researches[3]!.topic, created_at: T("2026-11-10T09:30:00Z") },
    { id: 7, research_id: 5, role: "user", content: researches[4]!.topic, created_at: T("2026-11-02T07:00:00Z") },
    {
      id: 8,
      research_id: 5,
      role: "assistant",
      content: "Three countries adjusted their schemes; details are in the panel.",
      created_at: T("2026-11-02T07:01:00Z"),
    },
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
      id: 41,
      research_id: FIXTURE_ACTIVE_RUN_ID,
      started_at: T("2026-11-10T09:30:00Z"),
      finished_at: null,
      status: "running",
      trigger: "chat",
      cost_cents: 0,
      new_findings: 0,
    },
    {
      id: 51,
      research_id: FIXTURE_CONFLICT_ID,
      started_at: T("2026-11-10T06:00:00Z"),
      finished_at: T("2026-11-10T06:01:00Z"),
      status: "ok",
      trigger: "watch",
      cost_cents: 18,
      new_findings: 1,
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
  /** Delay between simulated stream events, in ms (default 400; 0 in unit tests). */
  chunkDelayMs?: number;
  /** getResearch calls that still show a scripted run as active before it settles (default 2). */
  activeRunPolls?: number;
}

const wait = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

export function createMockClient(options: MockClientOptions = {}): ApiClient {
  const store = fixtures();
  const now = options.now ?? (() => new Date().toISOString());
  const chunkDelayMs = options.chunkDelayMs ?? 400;
  const activeRunPolls = options.activeRunPolls ?? 2;

  const scripted: ScriptedRun[] = [
    {
      researchId: FIXTURE_ACTIVE_RUN_ID,
      runId: 41,
      pollsLeft: activeRunPolls,
      reply:
        "Two groups reported logical qubits below the error threshold; the details and sources are in the panel.",
      finding: {
        title: "Logical qubit error rates fall below the surface-code threshold",
        url: "https://physics.example.org/news/logical-qubits-below-threshold",
        summary: "A 49-qubit surface-code experiment kept logical errors falling as the code distance grew.",
        source: "physics.example.org",
      },
    },
  ];
  /** Fixture B's watch run has not started yet. */
  let conflictRunPending = true;

  // React StrictMode mounts effects twice in dev, so calls in the same synchronous
  // turn count once; otherwise the fixtures would settle a poll early.
  const countedThisTurn = new Set<number>();
  const countCall = (id: number): boolean => {
    if (countedThisTurn.has(id)) return false;
    countedThisTurn.add(id);
    queueMicrotask(() => countedThisTurn.delete(id));
    return true;
  };

  const runningRun = (id: number): StoredRun | undefined =>
    store.runs.find((x) => x.research_id === id && x.status === "running");

  const addFinding = (researchId: number, f: ScriptedRun["finding"]): StoredFinding => {
    const stored: StoredFinding = {
      ...f,
      id: store.nextId++,
      research_id: researchId,
      found_at: now(),
      dismissed: false,
    };
    store.findings.push(stored);
    return stored;
  };

  const finishRun = (run: StoredRun, reply: string, newFindings: number, cost: number) => {
    const at = now();
    run.status = "ok";
    run.finished_at = at;
    run.cost_cents = cost;
    run.new_findings = newFindings;
    store.messages.push({ id: store.nextId++, research_id: run.research_id, role: "assistant", content: reply, created_at: at });
    const r = store.researches.find((x) => x.id === run.research_id);
    if (r) {
      r.last_run_at = at;
      r.last_activity_at = at;
    }
  };

  const advanceScripted = (id: number) => {
    for (const s of scripted) {
      if (s.researchId !== id) continue;
      const run = store.runs.find((x) => x.id === s.runId);
      if (!run || run.status !== "running") continue;
      if (s.pollsLeft > 0) {
        s.pollsLeft -= 1;
        continue;
      }
      addFinding(id, s.finding);
      finishRun(run, s.reply, 1, 21);
    }
  };

  const startConflictRun = () => {
    if (!conflictRunPending) return;
    conflictRunPending = false;
    if (!store.researches.some((x) => x.id === FIXTURE_CONFLICT_ID) || runningRun(FIXTURE_CONFLICT_ID)) return;
    const run: StoredRun = {
      id: store.nextId++,
      research_id: FIXTURE_CONFLICT_ID,
      started_at: now(),
      finished_at: null,
      status: "running",
      trigger: "watch",
      cost_cents: 0,
      new_findings: 0,
    };
    store.runs.push(run);
    // Counted from the next getResearch, like Fixture A.
    scripted.push({
      researchId: FIXTURE_CONFLICT_ID,
      runId: run.id,
      pollsLeft: activeRunPolls,
      reply: "New since the last check: one more country announced a subsidy change.",
      finding: {
        title: "Subsidy for air-to-water heat pumps raised to 40%",
        url: "https://energy.example.com/heat-pump-subsidy-raised",
        summary: "The ministry raised the grant ceiling and added an income bonus from January.",
        source: "energy.example.com",
      },
    });
  };

  /** Simulates one chat run: token chunks, one saved finding, then done; the run outlives the caller. */
  const simulateRun = async (
    researchId: number,
    userContent: string | null,
    handlers: RunStreamHandlers,
    signal?: AbortSignal,
  ): Promise<void> => {
    const at = now();
    const run: StoredRun = {
      id: store.nextId++,
      research_id: researchId,
      started_at: at,
      finished_at: null,
      status: "running",
      trigger: "chat",
      cost_cents: 0,
      new_findings: 0,
    };
    store.runs.push(run);
    if (userContent !== null) {
      store.messages.push({ id: store.nextId++, research_id: researchId, role: "user", content: userContent, created_at: at });
    }
    const r = find(researchId);
    r.last_activity_at = at;

    // A detached caller (abort) stops receiving events; the run itself keeps going (INV-11).
    const emit = (e: RunEvent) => {
      if (!signal?.aborted) handlers.onEvent(e);
    };
    handlers.onOpen?.();
    let reply = "";
    for (const chunk of MOCK_REPLY_CHUNKS) {
      await wait(chunkDelayMs);
      reply += chunk;
      emit({ type: "token", text: chunk });
    }
    await wait(chunkDelayMs);
    const n = run.id;
    const saved = addFinding(researchId, {
      title: `Mock finding for “${r.title}” (run ${n})`,
      url: `https://research.example.org/mock/${researchId}/${n}`,
      summary: "A deterministic finding saved by the simulated run, with its source link.",
      source: "research.example.org",
    });
    const { id, title, url, summary: s, source, found_at } = saved;
    emit({ type: "finding", finding: { id, title, url, summary: s, source, found_at } });
    await wait(chunkDelayMs);
    finishRun(run, reply, 1, 7);
    emit({ type: "done", run_id: run.id, status: "ok", cost_cents: 7, new_findings: 1 });
  };

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
      const counted = countCall(id);
      if (counted) advanceScripted(id);
      const running = runningRun(id);
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
          ? { id: running.id, trigger: running.trigger, started_at: running.started_at }
          : null,
      };
      if (id === FIXTURE_CONFLICT_ID && counted) queueMicrotask(startConflictRun);
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

    async sendMessage(researchId, content, handlers, signal) {
      find(researchId);
      const trimmed = content.trim();
      if (!trimmed) throw new ApiError(422, "content must not be blank");
      if (trimmed.length > MESSAGE_MAX_CHARS) {
        throw new ApiError(422, `content must be at most ${MESSAGE_MAX_CHARS} characters`);
      }
      if (runningRun(researchId)) throw new ApiError(409, RUN_IN_PROGRESS);
      await simulateRun(researchId, trimmed, handlers, signal);
    },

    async respond(researchId, handlers, signal) {
      find(researchId);
      if (runningRun(researchId)) throw new ApiError(409, RUN_IN_PROGRESS);
      const last = store.messages
        .filter((m) => m.research_id === researchId)
        .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id)
        .at(-1);
      if (!last || last.role !== "user") throw new ApiError(409, NO_PENDING_MESSAGE);
      await simulateRun(researchId, null, handlers, signal);
    },
  };
}

let singleton: ApiClient | null = null;

/** One store per page load, shared by every component. */
export function getMockClient(): ApiClient {
  singleton ??= createMockClient();
  return singleton;
}
