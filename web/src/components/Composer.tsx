"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

export type SendResult = "ok" | "conflict" | "error";

export const CONFLICT_TEXT = "Still working on the previous answer";

/** Message box pinned to the bottom of the thread. The draft is cleared only when the send is accepted. */
export function Composer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (content: string) => Promise<SendResult>;
}) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const canSend = !disabled && !sending && draft.trim().length > 0;

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!canSend) return;
    setSending(true);
    setNotice(null);
    const result = await onSend(draft.trim());
    setSending(false);
    if (result === "ok") setDraft("");
    else setNotice(result === "conflict" ? CONFLICT_TEXT : "Could not send the message");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void submit();
  };

  return (
    <form
      onSubmit={(e) => void submit(e)}
      aria-label="Send a message"
      className="border-t border-neutral-800 bg-neutral-950 px-3 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]"
    >
      {notice && (
        <p role="alert" className="pb-2 text-sm text-amber-300">
          {notice}
        </p>
      )}
      <div className="flex items-end gap-2">
        <textarea
          aria-label="Message"
          value={draft}
          rows={1}
          maxLength={2000}
          onChange={(e) => {
            setDraft(e.target.value);
            if (notice) setNotice(null);
          }}
          onKeyDown={onKeyDown}
          placeholder="Ask a follow-up…"
          className="max-h-40 min-h-11 min-w-0 flex-1 resize-none rounded-xl border border-neutral-700 bg-neutral-900 px-3 py-2.5 text-base text-neutral-100 placeholder:text-neutral-500 md:text-sm"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="min-h-11 shrink-0 rounded-xl bg-sky-600 px-4 font-medium text-white hover:bg-sky-500 disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </form>
  );
}
