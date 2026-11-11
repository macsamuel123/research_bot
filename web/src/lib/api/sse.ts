import type { Finding, RunEvent, RunStatus } from "./types";

/**
 * Incremental parser for the run SSE stream (`event: <name>\ndata: <json>\n\n`).
 * Accepts LF or CRLF line endings, joins multi-line `data:` fields, and ignores
 * comments, unknown event names and malformed payloads.
 */

const TERMINAL: readonly RunStatus[] = ["ok", "capped", "error"];

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isFinding(v: unknown): v is Finding {
  return (
    isRecord(v) &&
    typeof v.id === "number" &&
    typeof v.title === "string" &&
    typeof v.url === "string" &&
    typeof v.summary === "string" &&
    typeof v.source === "string" &&
    typeof v.found_at === "string"
  );
}

/** Turns one SSE frame (name + raw data) into a typed RunEvent, or null if unknown or malformed. */
export function toRunEvent(name: string, data: string): RunEvent | null {
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isRecord(payload)) return null;
  switch (name) {
    case "token":
      return typeof payload.text === "string" ? { type: "token", text: payload.text } : null;
    case "finding": {
      if (!isFinding(payload)) return null;
      const { id, title, url, summary, source, found_at } = payload;
      return { type: "finding", finding: { id, title, url, summary, source, found_at } };
    }
    case "done": {
      const { run_id, status, cost_cents, new_findings } = payload;
      if (
        typeof run_id !== "number" ||
        typeof status !== "string" ||
        !(TERMINAL as readonly string[]).includes(status) ||
        typeof cost_cents !== "number" ||
        typeof new_findings !== "number"
      ) {
        return null;
      }
      return {
        type: "done",
        run_id,
        status: status as Exclude<RunStatus, "running">,
        cost_cents,
        new_findings,
      };
    }
    case "error":
      return typeof payload.message === "string" ? { type: "error", message: payload.message } : null;
    default:
      return null;
  }
}

/** Stateful frame splitter; feed it decoded text, it returns the complete events seen so far. */
export class SseParser {
  private buffer = "";

  push(text: string): RunEvent[] {
    this.buffer += text.replace(/\r\n?/g, "\n");
    const events: RunEvent[] = [];
    let sep = this.buffer.indexOf("\n\n");
    while (sep !== -1) {
      const frame = this.buffer.slice(0, sep);
      this.buffer = this.buffer.slice(sep + 2);
      const event = parseFrame(frame);
      if (event) events.push(event);
      sep = this.buffer.indexOf("\n\n");
    }
    return events;
  }

  /** Call at end of stream: a trailing frame without the final blank line is still dispatched. */
  flush(): RunEvent[] {
    const rest = this.buffer;
    this.buffer = "";
    if (!rest.trim()) return [];
    const event = parseFrame(rest);
    return event ? [event] : [];
  }
}

function parseFrame(frame: string): RunEvent | null {
  let name = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") name = value;
    else if (field === "data") data.push(value);
  }
  if (data.length === 0) return null;
  return toRunEvent(name, data.join("\n"));
}

/** Reads a byte stream to the end, calling `onEvent` for every RunEvent in order. */
export async function readRunEvents(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: RunEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const e of parser.push(decoder.decode(value, { stream: true }))) onEvent(e);
    }
    for (const e of parser.push(decoder.decode())) onEvent(e);
    for (const e of parser.flush()) onEvent(e);
  } finally {
    reader.releaseLock();
  }
}
