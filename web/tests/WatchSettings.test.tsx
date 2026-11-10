import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WatchSettings } from "@/components/WatchSettings";
import { createMockClient } from "@/lib/api/mock";

import { renderWithList } from "./helpers";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/r/2",
}));

async function setup(id = 2) {
  const api = createMockClient();
  const items = await api.listResearches();
  const item = items.find((x) => x.id === id)!;
  renderWithList(
    <WatchSettings
      researchId={id}
      api={api}
      initial={{ watch_enabled: item.watch_enabled, schedule: item.schedule }}
    />,
    api,
    items,
  );
  return api;
}

function sidebarIndicator(id: number) {
  const nav = screen.getByRole("navigation", { name: "Researches" });
  const link = within(nav)
    .getAllByTestId("sidebar-item")
    .find((el) => el.getAttribute("data-research-id") === String(id))!;
  return within(link).getByRole("img", { name: /^watch (on|off)$/ });
}

beforeEach(() => push.mockReset());

// M7-C6 (unit level; Playwright covers the screens)
describe("WatchSettings", () => {
  it("toggle on sets daily and flips the sidebar indicator immediately", async () => {
    const api = await setup();
    const spy = vi.spyOn(api, "updateWatch");
    expect(sidebarIndicator(2)).toHaveAccessibleName("watch off");
    fireEvent.click(screen.getByRole("switch"));
    // Optimistic: flips in the same tick, before the client resolves.
    expect(sidebarIndicator(2)).toHaveAccessibleName("watch on");
    expect(spy).toHaveBeenCalledWith(2, { watch_enabled: true });
    await waitFor(() => expect(screen.getByRole("button", { name: "Daily" })).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("presets set the schedule and pause keeps it", async () => {
    const api = await setup();
    fireEvent.click(screen.getByRole("button", { name: "Weekly" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Weekly" })).toHaveAttribute("aria-pressed", "true"));
    expect(sidebarIndicator(2)).toHaveAccessibleName("watch on");
    fireEvent.click(screen.getByRole("button", { name: "Pause watch" }));
    await waitFor(() => expect(sidebarIndicator(2)).toHaveAccessibleName("watch off"));
    expect(screen.getByTestId("watch-status")).toHaveTextContent("Paused (was weekly)");
    expect((await api.getResearch(2)).schedule).toBe("weekly");
  });

  it("rolls back the indicator when the update fails", async () => {
    const api = await setup();
    vi.spyOn(api, "updateWatch").mockRejectedValue(new Error("down"));
    fireEvent.click(screen.getByRole("switch"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not update the watch");
    expect(sidebarIndicator(2)).toHaveAccessibleName("watch off");
  });

  it("delete: cancel keeps the research, confirm deletes and navigates home", async () => {
    const api = await setup();
    const del = vi.spyOn(api, "deleteResearch");
    fireEvent.click(screen.getByRole("button", { name: "Delete research" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(del).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete research" }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(del).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete research" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(del).toHaveBeenCalledWith(2);
    const nav = screen.getByRole("navigation", { name: "Researches" });
    expect(within(nav).queryByText("Solid-state battery startups")).not.toBeInTheDocument();
  });
});
