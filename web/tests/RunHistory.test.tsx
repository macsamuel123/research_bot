import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunHistory } from "@/components/RunHistory";
import { createMockClient } from "@/lib/api/mock";

// M7-C7
describe("RunHistory", () => {
  it("shows time, status badge, formatted cost and new-findings count per run", async () => {
    render(<RunHistory researchId={1} api={createMockClient()} />);
    const rows = await screen.findAllByTestId("run");
    expect(rows).toHaveLength(5);
    const statuses = rows.map((r) => r.querySelector("[data-status]")?.getAttribute("data-status"));
    expect(statuses).toEqual(["running", "ok", "capped", "error", "ok"]);
    const costs = rows.map((r) => within(r).getByTestId("run-cost").textContent);
    expect(costs).toEqual(["$0.00", "$12.34", "$0.50", "$0.05", "$0.00"]);
    const news = rows.map((r) => within(r).getByTestId("run-new").textContent);
    expect(news).toEqual(["0 new", "3 new", "1 new", "0 new", "0 new"]);
    for (const row of rows) {
      const time = row.querySelector("time");
      expect(time?.getAttribute("dateTime")).toMatch(/^\d{4}-\d{2}-\d{2}T/);
      expect(time?.textContent).toMatch(/^[A-Z][a-z]{2} \d{1,2}, \d{2}:\d{2}$/);
    }
  });

  it("shows an empty state", async () => {
    render(<RunHistory researchId={3} api={createMockClient()} />);
    expect(await screen.findByText("No runs yet.")).toBeInTheDocument();
  });
});
