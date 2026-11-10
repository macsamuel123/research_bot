"use client";

import { useEffect, useState } from "react";

import { getApiClient } from "@/lib/api/client";
import { ApiError, type ResearchDetail } from "@/lib/api/types";
import { DESKTOP_QUERY, useMediaQuery } from "@/lib/useMediaQuery";
import { useResearchList } from "@/lib/useResearchList";

import { BottomSheet } from "./BottomSheet";
import { ResearchPanel } from "./ResearchPanel";

export function Thread({ researchId }: { researchId: number }) {
  const { updateItem } = useResearchList();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const [research, setResearch] = useState<ResearchDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const api = getApiClient();
    api.getResearch(researchId).then(
      (r) => {
        if (cancelled) return;
        setResearch(r);
        if (r.unread) {
          updateItem({ id: r.id, unread: false });
          void api.markRead(r.id);
        }
      },
      (err: unknown) => {
        if (!cancelled && err instanceof ApiError && err.status === 404) setMissing(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [researchId, updateItem]);

  if (missing) return <p className="p-4 text-neutral-400">Research not found.</p>;
  if (!research) return <p className="p-4 text-neutral-400">Loading…</p>;

  const panel = (
    <ResearchPanel
      researchId={research.id}
      watch={{ watch_enabled: research.watch_enabled, schedule: research.schedule }}
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
        <ol aria-label="Messages" className="min-h-0 flex-1 overflow-y-auto p-4">
          {research.messages.map((m) => (
            <li
              key={m.id}
              data-role={m.role}
              className={`mb-3 max-w-[85%] rounded-2xl px-4 py-2 text-sm break-words ${
                m.role === "user"
                  ? "ml-auto bg-sky-700 text-white"
                  : "mr-auto bg-neutral-800 text-neutral-100"
              }`}
            >
              {m.content}
            </li>
          ))}
          {research.active_run && (
            <li role="status" className="text-xs text-neutral-400">
              Researching…
            </li>
          )}
        </ol>
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
