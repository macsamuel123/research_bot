import { afterEach, describe, expect, it } from "vitest";

import { ApiError, type RunStreamHandlers } from "@/lib/api/types";
import * as runStream from "@/lib/runStream";

/** A controllable stream: the test drives open/events/end. */
function controlled() {
  let handlers: RunStreamHandlers | null = null;
  let finish: () => void = () => {};
  let fail: (e: unknown) => void = () => {};
  const run = (h: RunStreamHandlers) => {
    handlers = h;
    return new Promise<void>((resolve, reject) => {
      finish = resolve;
      fail = reject;
    });
  };
  return {
    run,
    get h() {
      if (!handlers) throw new Error("not started");
      return handlers;
    },
    finish: () => finish(),
    fail: (e: unknown) => fail(e),
  };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => runStream.resetRunStreams());

describe("run-stream store", () => {
  it("accumulates tokens and findings and survives unsubscribe/resubscribe", async () => {
    const c = controlled();
    const started = runStream.start(1, c.run);
    const unsubscribe = runStream.subscribe(() => {});
    c.h.onOpen?.();
    expect(await started).toBe("started");
    c.h.onEvent({ type: "token", text: "Hel" });
    unsubscribe(); // e.g. Landing unmounts on router.push
    c.h.onEvent({ type: "token", text: "lo" });
    const again = runStream.subscribe(() => {});
    expect(runStream.get(1)).toMatchObject({ text: "Hello", status: "streaming" });
    c.h.onEvent({ type: "done", run_id: 9, status: "ok", cost_cents: 1, new_findings: 0 });
    expect(runStream.get(1)?.status).toBe("done");
    again();
  });

  it("a second start for the same id while streaming is a no-op", async () => {
    const c = controlled();
    void runStream.start(2, c.run);
    let calls = 0;
    const result = await runStream.start(2, async () => {
      calls += 1;
    });
    expect(result).toBe("busy");
    expect(calls).toBe(0);
  });

  it("rejects and leaves no entry when the request fails before opening", async () => {
    const c = controlled();
    const started = runStream.start(3, c.run);
    c.fail(new ApiError(409, "a run is already in progress"));
    await expect(started).rejects.toMatchObject({ status: 409 });
    expect(runStream.get(3)).toBeNull();
  });

  it("marks the entry done when the stream closes without a terminal event", async () => {
    const c = controlled();
    void runStream.start(4, c.run);
    c.h.onOpen?.();
    c.h.onEvent({ type: "token", text: "partial" });
    c.fail(new TypeError("network error"));
    await flush();
    expect(runStream.get(4)).toMatchObject({ status: "done", text: "partial" });
  });

  it("records error events and notifies per-id listeners with the previous entry", async () => {
    const c = controlled();
    const seen: [string | undefined, string | undefined][] = [];
    const off = runStream.subscribeTo(5, (next, prev) => seen.push([next?.status, prev?.status]));
    void runStream.start(5, c.run);
    c.h.onOpen?.();
    c.h.onEvent({ type: "error", message: "boom" });
    expect(runStream.get(5)).toMatchObject({ status: "error", error: "boom" });
    expect(seen.at(-1)).toEqual(["error", "streaming"]);
    runStream.clear(5);
    expect(runStream.get(5)).toBeNull();
    off();
  });

  it("clear keeps a streaming entry", () => {
    const c = controlled();
    void runStream.start(6, c.run);
    runStream.clear(6);
    expect(runStream.get(6)?.status).toBe("streaming");
  });
});
