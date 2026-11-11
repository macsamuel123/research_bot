import { describe, expect, it } from "vitest";

import { readRunEvents, SseParser } from "@/lib/api/sse";
import type { RunEvent } from "@/lib/api/types";

const finding = {
  id: 7,
  title: "T",
  url: "https://example.org/a",
  summary: "S",
  source: "example.org",
  found_at: "2026-11-10T10:00:00Z",
};

function streamOf(parts: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const p of parts) controller.enqueue(enc.encode(p));
      controller.close();
    },
  });
}

async function collect(parts: string[]): Promise<RunEvent[]> {
  const out: RunEvent[] = [];
  await readRunEvents(streamOf(parts), (e) => out.push(e));
  return out;
}

describe("SSE parser", () => {
  it("parses token, finding and done in order", async () => {
    const events = await collect([
      'event: token\ndata: {"text":"Hel"}\n\n',
      `event: finding\ndata: ${JSON.stringify(finding)}\n\n`,
      'event: done\ndata: {"run_id":3,"status":"ok","cost_cents":7,"new_findings":1}\n\n',
    ]);
    expect(events).toEqual([
      { type: "token", text: "Hel" },
      { type: "finding", finding },
      { type: "done", run_id: 3, status: "ok", cost_cents: 7, new_findings: 1 },
    ]);
  });

  it("handles frames split across chunks, including inside a multi-byte character", async () => {
    const bytes = new TextEncoder().encode('event: token\ndata: {"text":"café"}\n\n');
    const cut = bytes.length - 6; // inside "é"
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(bytes.slice(0, 5));
        c.enqueue(bytes.slice(5, cut));
        c.enqueue(bytes.slice(cut));
        c.close();
      },
    });
    const out: RunEvent[] = [];
    await readRunEvents(stream, (e) => out.push(e));
    expect(out).toEqual([{ type: "token", text: "café" }]);
  });

  it("joins multi-line data with newlines", () => {
    const p = new SseParser();
    expect(p.push('event: token\ndata: {"text":\ndata: "a\\nb"}\n\n')).toEqual([{ type: "token", text: "a\nb" }]);
  });

  it("accepts CRLF line endings", () => {
    const p = new SseParser();
    expect(p.push('event: error\r\ndata: {"message":"boom"}\r\n\r\n')).toEqual([
      { type: "error", message: "boom" },
    ]);
  });

  it("dispatches a trailing frame without the final blank line at end of stream", async () => {
    expect(await collect(['event: token\ndata: {"text":"x"}\n\nevent: token\ndata: {"text":"y"}'])).toEqual([
      { type: "token", text: "x" },
      { type: "token", text: "y" },
    ]);
  });

  it("ignores comments, unknown events and malformed payloads", async () => {
    expect(
      await collect([
        ": keep-alive\n\n",
        'event: ping\ndata: {"x":1}\n\n',
        "event: token\ndata: not json\n\n",
        'event: done\ndata: {"run_id":1,"status":"running","cost_cents":0,"new_findings":0}\n\n',
        'event: token\ndata: {"text":"ok"}\n\n',
      ]),
    ).toEqual([{ type: "token", text: "ok" }]);
  });
});
