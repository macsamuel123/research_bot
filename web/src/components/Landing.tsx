"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { getApiClient } from "@/lib/api/client";
import * as runStream from "@/lib/runStream";
import { useResearchList } from "@/lib/useResearchList";

export function Landing() {
  const router = useRouter();
  const { addItem } = useResearchList();
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const api = getApiClient();
      const created = await api.createResearch(topic);
      addItem(created);
      // The first turn: answer the pending topic message. This is the only place the UI
      // calls respond; the stream lives in the run-stream store and survives navigation.
      runStream.start(created.id, (handlers) => api.respond(created.id, handlers)).catch(() => {
        // Not started (e.g. 409): the thread shows the pending message and the owner can resend.
      });
      router.push(`/r/${created.id}`);
    } catch {
      setError("Could not start the research");
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-4">
      <form onSubmit={(e) => void submit(e)} className="flex w-full max-w-xl flex-col gap-3">
        <h1 className="text-center text-2xl font-semibold text-neutral-50">What do you want to research?</h1>
        <input
          aria-label="Research topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. EU AI Act enforcement"
          className="min-h-11 rounded-xl border border-neutral-700 bg-neutral-900 px-4 text-neutral-100 placeholder:text-neutral-500"
        />
        <button
          type="submit"
          disabled={busy || !topic.trim()}
          className="min-h-11 rounded-xl bg-sky-600 px-4 font-medium text-white hover:bg-sky-500 disabled:opacity-40"
        >
          Research
        </button>
        {error && (
          <p role="alert" className="text-sm text-red-400">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
