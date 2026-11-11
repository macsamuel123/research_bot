import { render } from "@testing-library/react";
import { vi } from "vitest";

import { ResearchListProvider } from "@/components/ResearchListProvider";
import { Thread } from "@/components/Thread";
import type { ApiClient } from "@/lib/api/client";

/** jsdom has no matchMedia; report a desktop viewport so the panel renders inline. */
export function stubDesktop(): void {
  vi.stubGlobal(
    "matchMedia",
    (query: string): MediaQueryList =>
      ({
        matches: true,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList,
  );
}

export function renderThread(researchId: number, api: ApiClient) {
  return render(
    <ResearchListProvider api={api} initialItems={[]}>
      <Thread researchId={researchId} api={api} />
    </ResearchListProvider>,
  );
}
