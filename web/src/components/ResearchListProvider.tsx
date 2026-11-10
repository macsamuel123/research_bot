"use client";

import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { getApiClient, type ApiClient } from "@/lib/api/client";
import type { ResearchSummary } from "@/lib/api/types";

export interface ResearchListState {
  items: ResearchSummary[];
  loaded: boolean;
  error: string | null;
  refresh(): Promise<void>;
  /** Puts a new research at the top of the sidebar. */
  addItem(item: ResearchSummary): void;
  /** Merges fields into an existing item (sidebar indicators update immediately). */
  updateItem(patch: Partial<ResearchSummary> & { id: number }): void;
  removeItem(id: number): void;
}

export const ResearchListContext = createContext<ResearchListState | null>(null);

function sortByActivity(items: ResearchSummary[]): ResearchSummary[] {
  return [...items].sort(
    (a, b) => b.last_activity_at.localeCompare(a.last_activity_at) || b.id - a.id,
  );
}

export function ResearchListProvider({
  children,
  api,
  initialItems,
}: {
  children: ReactNode;
  api?: ApiClient;
  /** Tests can seed the list instead of loading it. */
  initialItems?: ResearchSummary[];
}) {
  const client = useMemo(() => api ?? getApiClient(), [api]);
  const [items, setItems] = useState<ResearchSummary[]>(initialItems ?? []);
  const [loaded, setLoaded] = useState(initialItems !== undefined);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      client.listResearches().then(
        (list) => {
          setItems(sortByActivity(list));
          setError(null);
          setLoaded(true);
        },
        () => {
          setError("Could not load researches");
          setLoaded(true);
        },
      ),
    [client],
  );

  const refresh = useCallback(() => load(), [load]);

  const seeded = initialItems !== undefined;
  useEffect(() => {
    if (!seeded) void load();
  }, [seeded, load]);

  const addItem = useCallback((item: ResearchSummary) => {
    setItems((prev) => [item, ...prev.filter((x) => x.id !== item.id)]);
  }, []);

  const updateItem = useCallback((patch: Partial<ResearchSummary> & { id: number }) => {
    setItems((prev) => prev.map((x) => (x.id === patch.id ? { ...x, ...patch } : x)));
  }, []);

  const removeItem = useCallback((id: number) => {
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const value = useMemo<ResearchListState>(
    () => ({ items, loaded, error, refresh, addItem, updateItem, removeItem }),
    [items, loaded, error, refresh, addItem, updateItem, removeItem],
  );

  return <ResearchListContext.Provider value={value}>{children}</ResearchListContext.Provider>;
}
