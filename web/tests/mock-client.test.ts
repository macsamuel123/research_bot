import { describe, expect, it } from "vitest";

import { createMockClient } from "@/lib/api/mock";
import { ApiError, RUN_STATUSES, type Schedule } from "@/lib/api/types";

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
