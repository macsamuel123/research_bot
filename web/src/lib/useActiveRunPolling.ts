"use client";

import { useEffect, useRef } from "react";

export const ACTIVE_RUN_POLL_MS = 2000;

/**
 * While `activeRunId` is non-null, calls `poll` every `intervalMs`.
 * When it turns null after having been set, stops and calls `onSettled` once.
 */
export function useActiveRunPolling(
  activeRunId: number | null,
  poll: () => void,
  onSettled: () => void,
  intervalMs: number = ACTIVE_RUN_POLL_MS,
): void {
  const pollRef = useRef(poll);
  const settledRef = useRef(onSettled);
  const wasActive = useRef(false);

  useEffect(() => {
    pollRef.current = poll;
    settledRef.current = onSettled;
  });

  useEffect(() => {
    if (activeRunId === null) {
      if (wasActive.current) {
        wasActive.current = false;
        settledRef.current();
      }
      return;
    }
    wasActive.current = true;
    const handle = setInterval(() => pollRef.current(), intervalMs);
    return () => clearInterval(handle);
  }, [activeRunId, intervalMs]);
}
