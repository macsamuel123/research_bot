"use client";

import { useCallback, useSyncExternalStore } from "react";

import { get, subscribe, type RunStreamEntry } from "./runStream";

/** The current stream entry for a research, or null. */
export function useRunStream(researchId: number): RunStreamEntry | null {
  const snapshot = useCallback(() => get(researchId), [researchId]);
  return useSyncExternalStore(subscribe, snapshot, () => null);
}
