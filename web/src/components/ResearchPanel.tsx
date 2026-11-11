"use client";

import { useId, useState, type KeyboardEvent } from "react";

import type { ApiClient } from "@/lib/api/client";
import type { Schedule } from "@/lib/api/types";

import { FindingsPanel } from "./FindingsPanel";
import { RunHistory } from "./RunHistory";
import { WatchSettings } from "./WatchSettings";

export type PanelTab = "findings" | "watch" | "runs";

const TABS: { id: PanelTab; label: string }[] = [
  { id: "findings", label: "Findings" },
  { id: "watch", label: "Watch" },
  { id: "runs", label: "Runs" },
];

/** Findings / Watch / Runs tabs. The thread page puts this in a side panel (desktop) or a bottom sheet (mobile). */
export function ResearchPanel({
  researchId,
  watch,
  initialTab = "findings",
  api,
  refreshKey = 0,
}: {
  researchId: number;
  watch: { watch_enabled: boolean; schedule: Schedule | null };
  initialTab?: PanelTab;
  api?: ApiClient;
  /** Bumped by the thread when a run streams a finding or settles. */
  refreshKey?: number;
}) {
  const [tab, setTab] = useState<PanelTab>(initialTab);
  const baseId = useId();

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const i = TABS.findIndex((t) => t.id === tab);
    const next = TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
    if (next) setTab(next.id);
  };

  return (
    <div className="flex min-h-0 flex-col">
      <div
        role="tablist"
        aria-label="Research details"
        onKeyDown={onKeyDown}
        className="grid grid-cols-3 gap-1 border-b border-neutral-800 px-2"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`${baseId}-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`${baseId}-panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
            className={`min-h-11 border-b-2 text-sm font-medium ${
              tab === t.id
                ? "border-sky-400 text-neutral-50"
                : "border-transparent text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${tab}`}
        aria-labelledby={`${baseId}-tab-${tab}`}
        className="min-h-0 flex-1 overflow-y-auto"
      >
        {tab === "findings" && <FindingsPanel researchId={researchId} api={api} refreshKey={refreshKey} />}
        {tab === "watch" && <WatchSettings researchId={researchId} initial={watch} api={api} />}
        {tab === "runs" && <RunHistory researchId={researchId} api={api} refreshKey={refreshKey} />}
      </div>
    </div>
  );
}
