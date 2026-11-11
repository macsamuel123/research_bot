"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getApiClient, type ApiClient } from "@/lib/api/client";
import { ApiError, type ResearchDetail } from "@/lib/api/types";
import * as runStream from "@/lib/runStream";
import { useActiveRunPolling } from "@/lib/useActiveRunPolling";
import { DESKTOP_QUERY, useMediaQuery } from "@/lib/useMediaQuery";
import { useResearchList } from "@/lib/useResearchList";
import { useRunStream } from "@/lib/useRunStream";

import { BottomSheet } from "./BottomSheet";
import { Composer, type SendResult } from "./Composer";
import { MessageList } from "./MessageList";
import { ResearchPanel } from "./ResearchPanel";

/**
 * The thread at /r/<id>. Opening it never starts a run: the first turn is started by
 * Landing only, so a capped or errored run is never retried automatically (INV-9).
 */
export function Thread({ researchId, api }: { researchId: number; api?: ApiClient }) {
  const client = useMemo(() => api ?? getApiClient(), [api]);
  const { updateItem } = useResearchList();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const [research, setResearch] = useState<ResearchDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [runError, setRunError] = useState<string | null>(null);
  const stream = useRunStream(researchId);
  const streaming = stream?.status === "streaming";
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const refetch = useCallback(async (): Promise<void> => {
    try {
      const r = await client.getResearch(researchId);
      if (alive.current) setResearch(r);
    } catch (err: unknown) {
      if (alive.current && err instanceof ApiError && err.status === 404) setMissing(true);
    }
  }, [client, researchId]);

  const bumpPanel = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Initial load.
  useEffect(() => {
    let cancelled = false;
    client.getResearch(researchId).then(
      (r) => {
        if (cancelled) return;
        setResearch(r);
        if (r.unread) {
          updateItem({ id: r.id, unread: false });
          void client.markRead(r.id);
        }
      },
      (err: unknown) => {
        if (!cancelled && err instanceof ApiError && err.status === 404) setMissing(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [client, researchId, updateItem]);

  // A run we are not streaming ourselves (reload mid-run, watch, telegram): poll until it ends.
  const polledRunId = streaming ? null : (research?.active_run?.id ?? null);
  useActiveRunPolling(polledRunId, () => void refetch(), bumpPanel);

  // React to the stream: a new finding refreshes the panel; the end of the stream (done,
  // error or connection closed) refetches the persisted result. No run is started here.
  useEffect(() => {
    const settle = (entry: runStream.RunStreamEntry) => {
      void refetch().then(() => {
        if (!alive.current) return;
        if (entry.status === "error") setRunError(entry.error ?? "The research stopped with an error");
        bumpPanel();
        runStream.clear(researchId);
      });
    };
    const unsubscribe = runStream.subscribeTo(researchId, (entry, prev) => {
      if (!entry) return;
      if (entry.findings.length > (prev?.findings.length ?? 0)) bumpPanel();
      if (entry.status !== "streaming" && prev?.status === "streaming") settle(entry);
    });
    // A stream that ended while this thread was not mounted.
    const current = runStream.get(researchId);
    if (current && current.status !== "streaming") settle(current);
    return unsubscribe;
  }, [researchId, refetch, bumpPanel]);

  const onSend = async (content: string): Promise<SendResult> => {
    setRunError(null);
    try {
      const result = await runStream.start(
        researchId,
        (handlers) => client.sendMessage(researchId, content, handlers),
        {
          onOpen: () => {
            if (!alive.current) return;
            setResearch((prev) =>
              prev
                ? {
                    ...prev,
                    messages: [
                      ...prev.messages,
                      { id: -Date.now(), role: "user", content, created_at: new Date().toISOString() },
                    ],
                  }
                : prev,
            );
          },
        },
      );
      return result === "started" ? "ok" : "conflict";
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        // Another run (any trigger) is active: show it and poll until it ends.
        void refetch();
        return "conflict";
      }
      return "error";
    }
  };

  if (missing) return <p className="p-4 text-neutral-400">Research not found.</p>;
  if (!research) return <p className="p-4 text-neutral-400">Loading…</p>;

  const busy = research.active_run !== null || streaming;

  const panel = (
    <ResearchPanel
      researchId={research.id}
      watch={{ watch_enabled: research.watch_enabled, schedule: research.schedule }}
      refreshKey={refreshKey}
      api={api}
    />
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-neutral-800 px-4 py-1">
          <h1 className="min-w-0 flex-1 truncate py-2 text-base font-semibold text-neutral-50">
            {research.title}
          </h1>
          {!isDesktop && (
            <button
              type="button"
              onClick={() => setSheetOpen(true)}
              className="min-h-11 shrink-0 rounded-lg border border-neutral-700 px-3 text-sm text-neutral-200 hover:bg-neutral-800"
            >
              Details
            </button>
          )}
        </div>
        <MessageList
          messages={research.messages}
          streamingText={stream && stream.text ? stream.text : null}
          researching={busy}
        />
        {runError && (
          <p role="alert" className="px-4 pb-2 text-sm text-red-400">
            {runError}
          </p>
        )}
        <Composer disabled={busy} onSend={onSend} />
      </div>
      {isDesktop ? (
        <aside
          aria-label="Research details"
          className="flex w-96 shrink-0 flex-col border-l border-neutral-800 bg-neutral-950"
        >
          {panel}
        </aside>
      ) : (
        <BottomSheet open={sheetOpen} title="Research details" onClose={() => setSheetOpen(false)}>
          {panel}
        </BottomSheet>
      )}
    </div>
  );
}
