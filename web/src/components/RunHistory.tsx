"use client";

import { useEffect, useMemo, useState } from "react";

import { getApiClient, type ApiClient } from "@/lib/api/client";
import type { Run, RunStatus } from "@/lib/api/types";
import { formatCents, formatRunTime } from "@/lib/format";

const BADGE: Record<RunStatus, string> = {
  running: "bg-sky-900/60 text-sky-300 ring-sky-700",
  ok: "bg-emerald-900/60 text-emerald-300 ring-emerald-700",
  capped: "bg-amber-900/60 text-amber-300 ring-amber-700",
  error: "bg-red-900/60 text-red-300 ring-red-700",
};

export function RunHistory({ researchId, api }: { researchId: number; api?: ApiClient }) {
  const client = useMemo(() => api ?? getApiClient(), [api]);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client.listRuns(researchId).then(
      (list) => {
        if (!cancelled) setRuns(list);
      },
      () => {
        if (!cancelled) setError("Could not load run history");
      },
    );
    return () => {
      cancelled = true;
    };
  }, [client, researchId]);

  if (error) {
    return (
      <p role="alert" className="p-4 text-sm text-red-400">
        {error}
      </p>
    );
  }
  if (runs === null) return <p className="p-4 text-sm text-neutral-400">Loading runs…</p>;
  if (runs.length === 0) return <p className="p-4 text-sm text-neutral-400">No runs yet.</p>;

  return (
    <section aria-label="Run history" className="p-4">
      <ul className="flex flex-col divide-y divide-neutral-800">
        {runs.map((run) => (
          <li
            key={run.id}
            data-testid="run"
            className="flex min-w-0 items-center justify-between gap-3 py-3 text-sm"
          >
            <div className="flex min-w-0 flex-col gap-1">
              <time dateTime={run.started_at} className="text-neutral-200">
                {formatRunTime(run.started_at)}
              </time>
              <span className="text-xs text-neutral-500">{run.trigger}</span>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span
                data-status={run.status}
                className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${BADGE[run.status]}`}
              >
                {run.status}
              </span>
              <span data-testid="run-cost" className="w-16 text-right tabular-nums text-neutral-200">
                {formatCents(run.cost_cents)}
              </span>
              <span data-testid="run-new" className="w-12 text-right tabular-nums text-neutral-400">
                {run.new_findings} new
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
