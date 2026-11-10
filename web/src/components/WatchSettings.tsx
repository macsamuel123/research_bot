"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { getApiClient, type ApiClient } from "@/lib/api/client";
import type { Schedule, WatchPatch } from "@/lib/api/types";
import { useResearchList } from "@/lib/useResearchList";

import { ConfirmDialog } from "./ConfirmDialog";

const PRESETS: { value: Schedule; label: string }[] = [
  { value: "6h", label: "Every 6h" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
];

const SCHEDULE_TEXT: Record<Schedule, string> = {
  "6h": "every 6 hours",
  daily: "daily",
  weekly: "weekly",
};

interface WatchState {
  watch_enabled: boolean;
  schedule: Schedule | null;
}

export function WatchSettings({
  researchId,
  initial,
  api,
}: {
  researchId: number;
  /** Used until the sidebar list (the source of truth) has the item. */
  initial: WatchState;
  api?: ApiClient;
}) {
  const client = useMemo(() => api ?? getApiClient(), [api]);
  const router = useRouter();
  const { items, updateItem, removeItem } = useResearchList();
  const item = items.find((x) => x.id === researchId);
  const current: WatchState = item
    ? { watch_enabled: item.watch_enabled, schedule: item.schedule }
    : initial;

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  /** Optimistic: the sidebar indicator flips right away, and rolls back on failure. */
  const apply = async (patch: WatchPatch, optimistic: WatchState) => {
    const before = current;
    setPending(true);
    setError(null);
    updateItem({ id: researchId, ...optimistic });
    try {
      const result = await client.updateWatch(researchId, patch);
      updateItem(result);
    } catch {
      updateItem({ id: researchId, ...before });
      setError("Could not update the watch");
    } finally {
      setPending(false);
    }
  };

  const toggle = () => {
    if (current.watch_enabled) {
      void apply({ watch_enabled: false }, { ...current, watch_enabled: false });
    } else {
      void apply(
        { watch_enabled: true },
        { watch_enabled: true, schedule: current.schedule ?? "daily" },
      );
    }
  };

  const choose = (schedule: Schedule) => {
    void apply({ watch_enabled: true, schedule }, { watch_enabled: true, schedule });
  };

  const pause = () => {
    void apply({ watch_enabled: false }, { ...current, watch_enabled: false });
  };

  const confirmDelete = async () => {
    setDeleting(true);
    setError(null);
    try {
      await client.deleteResearch(researchId);
      removeItem(researchId);
      setConfirmOpen(false);
      router.push("/");
    } catch {
      setError("Could not delete the research");
      setConfirmOpen(false);
    } finally {
      setDeleting(false);
    }
  };

  const status = current.watch_enabled
    ? `Watching ${SCHEDULE_TEXT[current.schedule ?? "daily"]}`
    : current.schedule
      ? `Paused (was ${SCHEDULE_TEXT[current.schedule]})`
      : "Not watching";

  return (
    <section aria-label="Watch settings" className="flex flex-col gap-5 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p id={`watch-label-${researchId}`} className="text-sm font-medium text-neutral-100">
            Watch this research
          </p>
          <p data-testid="watch-status" className="text-xs text-neutral-400">
            {status}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={current.watch_enabled}
          aria-labelledby={`watch-label-${researchId}`}
          onClick={toggle}
          disabled={pending}
          className="flex min-h-11 min-w-16 shrink-0 items-center justify-center disabled:opacity-60"
        >
          <span
            aria-hidden="true"
            className={`relative inline-flex h-7 w-12 rounded-full transition-colors ${
              current.watch_enabled ? "bg-emerald-600" : "bg-neutral-700"
            }`}
          >
            <span
              className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform ${
                current.watch_enabled ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </span>
        </button>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium tracking-wide text-neutral-400 uppercase">Schedule</p>
        <div role="group" aria-label="Schedule" className="grid grid-cols-3 gap-2">
          {PRESETS.map((p) => {
            const pressed = current.watch_enabled && current.schedule === p.value;
            return (
              <button
                key={p.value}
                type="button"
                aria-pressed={pressed}
                onClick={() => choose(p.value)}
                disabled={pending}
                className={`min-h-11 rounded-xl border px-2 text-sm disabled:opacity-60 ${
                  pressed
                    ? "border-emerald-500 bg-emerald-900/40 text-emerald-200"
                    : "border-neutral-700 text-neutral-200 hover:bg-neutral-800"
                }`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      <button
        type="button"
        onClick={pause}
        disabled={pending || !current.watch_enabled}
        className="min-h-11 rounded-xl border border-neutral-700 px-4 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
      >
        Pause watch
      </button>

      {error && (
        <p role="alert" className="text-sm text-red-400">
          {error}
        </p>
      )}

      <div className="border-t border-neutral-800 pt-4">
        <button
          type="button"
          onClick={() => setConfirmOpen(true)}
          className="min-h-11 w-full rounded-xl border border-red-800 px-4 text-sm text-red-300 hover:bg-red-950"
        >
          Delete research
        </button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete this research?"
        body="Its messages, findings and run history will be removed. This cannot be undone."
        confirmLabel="Delete"
        busy={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </section>
  );
}
