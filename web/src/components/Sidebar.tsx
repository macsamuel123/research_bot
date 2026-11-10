"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { formatRelative } from "@/lib/format";
import { useResearchList } from "@/lib/useResearchList";

export function Sidebar() {
  const { items, loaded, error } = useResearchList();
  const pathname = usePathname();

  return (
    <nav aria-label="Researches" className="flex h-full min-h-0 flex-col">
      <div className="p-3">
        <Link
          href="/"
          className="flex min-h-11 items-center justify-center rounded-xl bg-sky-600 px-4 text-sm font-medium text-white hover:bg-sky-500"
        >
          New research
        </Link>
      </div>
      {error && (
        <p role="alert" className="px-4 text-sm text-red-400">
          {error}
        </p>
      )}
      {loaded && items.length === 0 && !error && (
        <p className="px-4 text-sm text-neutral-500">No researches yet.</p>
      )}
      <ul className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {items.map((r) => {
          const href = `/r/${r.id}`;
          const active = pathname === href;
          return (
            <li key={r.id}>
              <Link
                href={href}
                data-testid="sidebar-item"
                data-research-id={r.id}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                  active ? "bg-neutral-800 text-neutral-50" : "text-neutral-300 hover:bg-neutral-900"
                }`}
              >
                <span className="min-w-0 flex-1 truncate">{r.title}</span>
                {r.unread && (
                  <span role="img" aria-label="unread" className="h-2 w-2 shrink-0 rounded-full bg-sky-400" />
                )}
                <span
                  role="img"
                  aria-label={r.watch_enabled ? "watch on" : "watch off"}
                  title={r.watch_enabled ? "Watch on" : "Watch off"}
                  className={`shrink-0 text-xs ${r.watch_enabled ? "text-emerald-400" : "text-neutral-600"}`}
                >
                  {r.watch_enabled ? "◉" : "○"}
                </span>
                <span className="shrink-0 text-xs text-neutral-500">{formatRelative(r.last_activity_at)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
