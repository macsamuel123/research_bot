"use client";

import { useEffect, useMemo, useState } from "react";

import { getApiClient, type ApiClient } from "@/lib/api/client";
import type { Finding } from "@/lib/api/types";

export function FindingsPanel({ researchId, api }: { researchId: number; api?: ApiClient }) {
  const client = useMemo(() => api ?? getApiClient(), [api]);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client.listFindings(researchId).then(
      (list) => {
        if (!cancelled) setFindings(list);
      },
      () => {
        if (!cancelled) setError("Could not load findings");
      },
    );
    return () => {
      cancelled = true;
    };
  }, [client, researchId]);

  const dismiss = async (finding: Finding) => {
    const before = findings;
    setFindings((prev) => prev?.filter((f) => f.id !== finding.id) ?? null);
    setError(null);
    try {
      await client.dismissFinding(finding.id);
    } catch {
      setFindings(before);
      setError("Could not dismiss the finding");
    }
  };

  if (findings === null && !error) {
    return <p className="p-4 text-sm text-neutral-400">Loading findings…</p>;
  }

  return (
    <section aria-label="Findings" className="flex flex-col gap-3 p-4">
      {error && (
        <p role="alert" className="text-sm text-red-400">
          {error}
        </p>
      )}
      {findings && findings.length === 0 && (
        <p className="text-sm text-neutral-400">No findings yet. Ask a question to start researching.</p>
      )}
      <ul className="flex flex-col gap-3">
        {findings?.map((f) => (
          <li
            key={f.id}
            data-testid="finding"
            className="min-w-0 rounded-xl border border-neutral-800 bg-neutral-900/60 p-3"
          >
            <h3 className="text-sm font-semibold break-words text-neutral-100">{f.title}</h3>
            <p className="mt-1 text-sm break-words text-neutral-300">{f.summary}</p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <a
                href={f.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-11 min-w-0 items-center truncate text-sm text-sky-400 underline-offset-2 hover:underline"
              >
                <span className="truncate">{f.source}</span>
              </a>
              <button
                type="button"
                onClick={() => void dismiss(f)}
                aria-label={`Dismiss: ${f.title}`}
                className="min-h-11 shrink-0 rounded-lg px-3 text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-100"
              >
                Dismiss
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
