import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FindingsPanel } from "@/components/FindingsPanel";
import { createMockClient } from "@/lib/api/mock";

// M7-C5
describe("FindingsPanel", () => {
  it("shows title, summary and a safe external source link for each finding", async () => {
    render(<FindingsPanel researchId={1} api={createMockClient()} />);
    const items = await screen.findAllByTestId("finding");
    expect(items).toHaveLength(4);
    const first = items[0]!;
    expect(within(first).getByRole("heading")).toHaveTextContent("AI Office opens first formal inquiry");
    expect(first).toHaveTextContent("The AI Office requested technical documentation");
    const link = within(first).getByRole("link", { name: "digital-strategy.example.eu" });
    expect(link).toHaveAttribute("href", "https://digital-strategy.example.eu/news/ai-office-first-inquiry");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("dismiss removes the item and calls the client", async () => {
    const api = createMockClient();
    const spy = vi.spyOn(api, "dismissFinding");
    render(<FindingsPanel researchId={1} api={api} />);
    await screen.findAllByTestId("finding");
    fireEvent.click(screen.getByRole("button", { name: /Dismiss: Germany designates/ }));
    await waitFor(() => expect(screen.getAllByTestId("finding")).toHaveLength(3));
    expect(screen.queryByText(/Germany designates/)).not.toBeInTheDocument();
    expect(spy).toHaveBeenCalledWith(102);
    expect((await api.listFindings(1)).map((f) => f.id)).not.toContain(102);
  });

  it("restores the item if dismiss fails", async () => {
    const api = createMockClient();
    vi.spyOn(api, "dismissFinding").mockRejectedValue(new Error("boom"));
    render(<FindingsPanel researchId={1} api={api} />);
    await screen.findAllByTestId("finding");
    fireEvent.click(screen.getByRole("button", { name: /Dismiss: Germany designates/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not dismiss");
    expect(screen.getAllByTestId("finding")).toHaveLength(4);
  });

  it("shows an empty state", async () => {
    render(<FindingsPanel researchId={3} api={createMockClient()} />);
    expect(await screen.findByText(/No findings yet/)).toBeInTheDocument();
  });
});
