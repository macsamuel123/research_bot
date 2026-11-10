"use client";

import { type ReactNode } from "react";

export function Drawer({ open, onClose, children }: { open: boolean; onClose(): void; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-30 lg:hidden">
      <button
        type="button"
        aria-label="Close menu"
        onClick={onClose}
        className="absolute inset-0 h-full w-full bg-black/60"
      />
      <div className="absolute inset-y-0 left-0 flex w-[85vw] max-w-xs flex-col border-r border-neutral-800 bg-neutral-950 pt-[env(safe-area-inset-top)]">
        {children}
      </div>
    </div>
  );
}
