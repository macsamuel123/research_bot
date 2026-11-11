import { describe, expect, it } from "vitest";

import {
  createMockClient,
  FIXTURE_ACTIVE_RUN_ID,
  FIXTURE_CONFLICT_ID,
  MOCK_REPLY_CHUNKS,
  NO_PENDING_MESSAGE,
  RUN_IN_PROGRESS,
} from "@/lib/api/mock";
import { ApiError, RUN_STATUSES, type RunEvent, type Schedule } from "@/lib/api/types";

function clock() {
  let t = Date.parse("2026-11-10T10:00:00Z");
  return {
    now: () => new Date(t).toISOString(),
    advance: (ms: number) => {
      t += ms;
    },
  };
}

describe("mock ApiClient fixtures", () => {
  it("returns identical findings and runs on every fresh store", async () => {
    const a = createMockClient();
    const b = createMockClient();
    expect(await a.listFindings(1)).toEqual(await b.listFindings(1));
    expect(await a.listRuns(1)).toEqual(await b.listRuns(1));
    expect(await a.listResearches()).toEqual(await b.listResearches());
  });

  it("lists non-dismissed findings newest first with exactly the API fields", async () => {
    const api = createMockClient();
    const findings = await api.listFindings(1);
    expect(findings.map((f) => f.id)).toEqual([101, 102, 103, 104]);
    for (const f of findings) {
      expect(Object.keys(f).sort()).toEqual(["found_at", "id", "source", "summary", "title", "url"]);
      expect(f.url).toMatch(/^https?:\/\//);
    }
  });

  it("lists runs newest first covering every status with integer costs", async () => {
    const runs = await createMockClient().listRuns(1);
    const starts = runs.map((r) => r.started_at);
    expect(starts).toEqual([...starts].sort().reverse());
    expect(new Set(runs.map((r) => r.status))).toEqual(new Set(RUN_STATUSES));
    expect(runs.every((r) => Number.isInteger(r.cost_cents))).toBe(true);
    expect(runs.map((r) => r.cost_cents)).toEqual(expect.arrayContaining([0, 5, 1234, 50]));
  });

  it("dismiss is idempotent and hides the finding; unknown id is 404", async () => {
    const api = createMockClient();
    await api.dismissFinding(102);
    await api.dismissFinding(102);
    expect((await api.listFindings(1)).map((f) => f.id)).toEqual([101, 103, 104]);
    await expect(api.dismissFinding(999_999)).rejects.toMatchObject({ status: 404 });
  });
});

describe("mock updateWatch mirrors the backend rules (M7-C2)", () => {
  it("enabling with no schedule sets daily and watch_enabled_at = now", async () => {
    const c = clock();
    const api = createMockClient({ now: c.now });
    const r = await api.updateWatch(2, { watch_enabled: true });
    expect(r).toMatchObject({ watch_enabled: true, schedule: "daily" });
    expect((await api.getResearch(2)).watch_enabled_at).toBe(c.now());
  });

  it("changing the schedule moves watch_enabled_at; resending the same does not", async () => {
    const c = clock();
    const api = createMockClient({ now: c.now });
    await api.updateWatch(2, { watch_enabled: true });
    const first = (await api.getResearch(2)).watch_enabled_at;
    c.advance(60_000);
    await api.updateWatch(2, { watch_enabled: true, schedule: "daily" });
    expect((await api.getResearch(2)).watch_enabled_at).toBe(first);
    await api.updateWatch(2, { schedule: "weekly" });
    expect((await api.getResearch(2)).watch_enabled_at).toBe(c.now());
  });

  it("pausing keeps the schedule and watch_enabled_at", async () => {
    const api = createMockClient();
    const before = await api.getResearch(1);
    const r = await api.updateWatch(1, { watch_enabled: false });
    expect(r).toMatchObject({ watch_enabled: false, schedule: "daily" });
    expect((await api.getResearch(1)).watch_enabled_at).toBe(before.watch_enabled_at);
  });

  it.each(["hourly", "", "DAILY"])("rejects schedule %j with 422", async (bad) => {
    const api = createMockClient();
    const err: unknown = await api.updateWatch(1, { schedule: bad as Schedule }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(422);
    expect((await api.getResearch(1)).schedule).toBe("daily");
  });
});

describe("mock deleteResearch", () => {
  it("removes the research with its findings, runs and messages", async () => {
    const api = createMockClient();
    await api.deleteResearch(1);
    expect((await api.listResearches()).map((r) => r.id)).not.toContain(1);
    await expect(api.getResearch(1)).rejects.toMatchObject({ status: 404 });
    await expect(api.listFindings(1)).rejects.toMatchObject({ status: 404 });
    await expect(api.listRuns(1)).rejects.toMatchObject({ status: 404 });
    await expect(api.deleteResearch(1)).rejects.toMatchObject({ status: 404 });
    expect(await api.listFindings(2)).toHaveLength(2);
  });
});

describe("mock streaming mirrors the backend run rules (M9)", () => {
  const collect = () => {
    const events: RunEvent[] = [];
    let opened = 0;
    return { events, handlers: { onOpen: () => (opened += 1), onEvent: (e: RunEvent) => events.push(e) }, opened: () => opened };
  };

  it("sendMessage stores the user message on open, streams token→finding→done and persists the reply", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    const before = (await api.getResearch(2)).messages.length;
    const c = collect();
    await api.sendMessage(2, "  any news?  ", c.handlers);
    expect(c.opened()).toBe(1);
    const types = c.events.map((e) => e.type);
    expect(types.slice(0, MOCK_REPLY_CHUNKS.length)).toEqual(MOCK_REPLY_CHUNKS.map(() => "token"));
    expect(types.slice(MOCK_REPLY_CHUNKS.length)).toEqual(["finding", "done"]);
    const done = c.events.at(-1);
    expect(done).toMatchObject({ type: "done", status: "ok", new_findings: 1 });
    const after = await api.getResearch(2);
    expect(after.messages.length).toBe(before + 2);
    expect(after.messages.at(-2)).toMatchObject({ role: "user", content: "any news?" });
    expect(after.messages.at(-1)).toMatchObject({ role: "assistant", content: MOCK_REPLY_CHUNKS.join("") });
    expect(after.active_run).toBeNull();
    const finding = c.events.find((e) => e.type === "finding");
    expect((await api.listFindings(2)).map((f) => f.id)).toContain(
      finding?.type === "finding" ? finding.finding.id : -1,
    );
  });

  it("returns 409 while any run is active and stores no message", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    const before = (await api.getResearch(1)).messages.length; // run 15 is running
    await expect(api.sendMessage(1, "hi", collect().handlers)).rejects.toEqual(new ApiError(409, RUN_IN_PROGRESS));
    await expect(api.respond(1, collect().handlers)).rejects.toMatchObject({ status: 409 });
    expect((await api.getResearch(1)).messages.length).toBe(before);
  });

  it("respond answers a pending user message and 409s when the last message is not a user one", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    await expect(api.respond(2, collect().handlers)).rejects.toEqual(new ApiError(409, NO_PENDING_MESSAGE));
    const runsBefore = (await api.listRuns(2)).length;
    expect(runsBefore).toBe(1);
    const created = await api.createResearch("New topic");
    const pending = await api.getResearch(created.id);
    expect(pending.messages).toEqual([expect.objectContaining({ role: "user", content: "New topic" })]);
    await api.respond(created.id, collect().handlers);
    const answered = await api.getResearch(created.id);
    expect(answered.messages.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(await api.listRuns(created.id)).toHaveLength(1);
  });

  it("rejects blank or oversized content with 422", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    await expect(api.sendMessage(2, "   ", collect().handlers)).rejects.toMatchObject({ status: 422 });
    await expect(api.sendMessage(2, "x".repeat(2001), collect().handlers)).rejects.toMatchObject({ status: 422 });
    await expect(api.sendMessage(999, "hi", collect().handlers)).rejects.toMatchObject({ status: 404 });
  });

  it("Fixture A settles after `activeRunPolls` polls with a reply and a finding", async () => {
    const api = createMockClient({ activeRunPolls: 2 });
    const findingsBefore = (await api.listFindings(FIXTURE_ACTIVE_RUN_ID)).length;
    const r1 = await api.getResearch(FIXTURE_ACTIVE_RUN_ID);
    expect(Object.keys(r1.active_run ?? {}).sort()).toEqual(["id", "started_at", "trigger"]);
    expect((await api.getResearch(FIXTURE_ACTIVE_RUN_ID)).active_run).not.toBeNull();
    const settled = await api.getResearch(FIXTURE_ACTIVE_RUN_ID);
    expect(settled.active_run).toBeNull();
    expect(settled.messages.at(-1)?.role).toBe("assistant");
    expect(await api.listFindings(FIXTURE_ACTIVE_RUN_ID)).toHaveLength(findingsBefore + 1);
    expect((await api.listRuns(FIXTURE_ACTIVE_RUN_ID))[0]?.status).toBe("ok");
  });

  it("Fixture B starts a watch run after the first load, so a send gets 409", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    expect((await api.getResearch(FIXTURE_CONFLICT_ID)).active_run).toBeNull();
    await expect(api.sendMessage(FIXTURE_CONFLICT_ID, "hi", collect().handlers)).rejects.toMatchObject({
      status: 409,
    });
    expect((await api.getResearch(FIXTURE_CONFLICT_ID)).active_run).toMatchObject({ trigger: "watch" });
  });

  it("calls in the same synchronous turn (StrictMode double mount) count as one poll", async () => {
    const api = createMockClient({ activeRunPolls: 1 });
    const [a, b] = await Promise.all([api.getResearch(FIXTURE_ACTIVE_RUN_ID), api.getResearch(FIXTURE_ACTIVE_RUN_ID)]);
    expect(a.active_run).not.toBeNull();
    expect(b.active_run).not.toBeNull();
    expect((await api.getResearch(FIXTURE_ACTIVE_RUN_ID)).active_run).toBeNull();
  });
});
