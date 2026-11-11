"use client";

import { useEffect, useRef } from "react";

import type { Message } from "@/lib/api/types";

const bubble = "mb-3 max-w-[85%] rounded-2xl px-4 py-2 text-sm break-words whitespace-pre-wrap";

/** Persisted messages, the streaming assistant reply, and the "Researching…" status. */
export function MessageList({
  messages,
  streamingText,
  researching,
}: {
  messages: Message[];
  /** Partial assistant text of the current stream, or null when none is shown. */
  streamingText: string | null;
  researching: boolean;
}) {
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, streamingText, researching]);

  return (
    <ol ref={listRef} aria-label="Messages" className="min-h-0 flex-1 overflow-y-auto p-4">
      {messages.map((m) => (
        <li
          key={m.id}
          data-role={m.role}
          className={`${bubble} ${
            m.role === "user" ? "ml-auto bg-sky-700 text-white" : "mr-auto bg-neutral-800 text-neutral-100"
          }`}
        >
          {m.content}
        </li>
      ))}
      {streamingText ? (
        <li data-role="assistant" data-streaming="true" className={`${bubble} mr-auto bg-neutral-800 text-neutral-100`}>
          {streamingText}
        </li>
      ) : null}
      {researching && (
        <li role="status" className="flex items-center gap-2 text-xs text-neutral-400">
          <span aria-hidden="true" className="inline-block h-2 w-2 animate-pulse rounded-full bg-sky-400" />
          Researching…
        </li>
      )}
    </ol>
  );
}
