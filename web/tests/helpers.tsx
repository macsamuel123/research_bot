import { render } from "@testing-library/react";
import type { ReactElement } from "react";

import { ResearchListProvider } from "@/components/ResearchListProvider";
import { Sidebar } from "@/components/Sidebar";
import type { ApiClient } from "@/lib/api/client";
import type { ResearchSummary } from "@/lib/api/types";

export function renderWithList(ui: ReactElement, api: ApiClient, items: ResearchSummary[]) {
  return render(
    <ResearchListProvider api={api} initialItems={items}>
      <Sidebar />
      {ui}
    </ResearchListProvider>,
  );
}
