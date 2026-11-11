import type { Finding, RunEvent, RunStreamHandlers } from "@/lib/api/types";

/**
 * Module-level store of in-flight run streams, keyed by research id.
 * Lives outside React so a stream started on Landing survives `router.push`
 * and StrictMode double mounts. Unsubscribing never aborts a stream.
 */

export type RunStreamStatus = "streaming" | "done" | "error";

export interface RunStreamEntry {
  text: string;
  findings: Finding[];
  status: RunStreamStatus;
  /** Message of an `error` event. */
  error: string | null;
}

export type StartResult = "started" | "busy";

export interface StartHooks {
  /** Called when the server accepted the request, before any event. */
  onOpen?(): void;
}

export type EntryListener = (entry: RunStreamEntry | null, prev: RunStreamEntry | null) => void;

const entries = new Map<number, RunStreamEntry>();
const listeners = new Set<() => void>();
const entryListeners = new Map<number, Set<EntryListener>>();

function set(id: number, entry: RunStreamEntry | null): void {
  const prev = entries.get(id) ?? null;
  if (entry) entries.set(id, entry);
  else entries.delete(id);
  for (const l of listeners) l();
  for (const l of entryListeners.get(id) ?? []) l(entry, prev);
}

function apply(id: number, event: RunEvent): void {
  const cur = entries.get(id);
  if (!cur || cur.status !== "streaming") return;
  switch (event.type) {
    case "token":
      set(id, { ...cur, text: cur.text + event.text });
      break;
    case "finding":
      set(id, { ...cur, findings: [...cur.findings, event.finding] });
      break;
    case "done":
      set(id, { ...cur, status: "done" });
      break;
    case "error":
      set(id, { ...cur, status: "error", error: event.message });
      break;
  }
}

function close(id: number): void {
  const cur = entries.get(id);
  // Stream ended without a terminal event (e.g. connection lost): the run may still be
  // going server-side, so the thread refetches and polls `active_run` from here.
  if (cur?.status === "streaming") set(id, { ...cur, status: "done" });
}

/**
 * Starts a stream for `id` unless one is already streaming (then "busy", no call).
 * Resolves "started" once the request is accepted; rejects with the request's error
 * (e.g. ApiError 409) if it fails before opening, and then leaves no entry behind.
 */
export function start(
  id: number,
  run: (handlers: RunStreamHandlers) => Promise<void>,
  hooks: StartHooks = {},
): Promise<StartResult> {
  if (entries.get(id)?.status === "streaming") return Promise.resolve("busy");
  set(id, { text: "", findings: [], status: "streaming", error: null });
  return new Promise<StartResult>((resolve, reject) => {
    let opened = false;
    const open = () => {
      if (opened) return;
      opened = true;
      hooks.onOpen?.();
      resolve("started");
    };
    let promise: Promise<void>;
    try {
      promise = run({ onOpen: open, onEvent: (e) => apply(id, e) });
    } catch (err) {
      promise = Promise.reject(err);
    }
    promise.then(
      () => {
        open();
        close(id);
      },
      (err: unknown) => {
        if (!opened) {
          set(id, null);
          reject(err);
        } else {
          close(id);
        }
      },
    );
  });
}

export function get(id: number): RunStreamEntry | null {
  return entries.get(id) ?? null;
}

/** Drops a terminal entry once the thread has refetched the persisted result. */
export function clear(id: number): void {
  const cur = entries.get(id);
  if (cur && cur.status !== "streaming") set(id, null);
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Calls `listener` with (next, previous) on every change to one research's entry. */
export function subscribeTo(id: number, listener: EntryListener): () => void {
  let forId = entryListeners.get(id);
  if (!forId) {
    forId = new Set();
    entryListeners.set(id, forId);
  }
  forId.add(listener);
  return () => {
    const s = entryListeners.get(id);
    s?.delete(listener);
    if (s?.size === 0) entryListeners.delete(id);
  };
}

/** Test-only: forget every entry. */
export function resetRunStreams(): void {
  entries.clear();
  for (const l of listeners) l();
}
