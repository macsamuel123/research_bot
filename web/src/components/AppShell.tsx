"use client";

import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Drawer } from "./Drawer";
import { ResearchListProvider } from "./ResearchListProvider";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // The drawer remembers the path it was opened on, so it closes on navigation.
  const [openedOn, setOpenedOn] = useState<string | null>(null);
  const drawerOpen = openedOn !== null && openedOn === pathname;
  const setDrawerOpen = (open: boolean) => setOpenedOn(open ? pathname : null);

  return (
    <ResearchListProvider>
      <div className="flex h-dvh overflow-hidden">
        <aside className="hidden w-72 shrink-0 border-r border-neutral-800 bg-neutral-950 lg:flex lg:flex-col">
          <Sidebar />
        </aside>
        <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          <Sidebar />
        </Drawer>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center gap-2 border-b border-neutral-800 px-2 pt-[env(safe-area-inset-top)] lg:hidden">
            <button
              type="button"
              aria-label="Open menu"
              aria-expanded={drawerOpen}
              onClick={() => setDrawerOpen(true)}
              className="min-h-11 min-w-11 rounded-lg text-xl text-neutral-200 hover:bg-neutral-800"
            >
              ☰
            </button>
            <span className="text-sm font-semibold text-neutral-200">Research Bot</span>
          </header>
          <main className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</main>
        </div>
      </div>
    </ResearchListProvider>
  );
}
