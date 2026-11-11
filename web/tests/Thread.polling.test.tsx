import { act, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createMockClient, FIXTURE_ACTIVE_RUN_ID } from "@/lib/api/mock";
import { resetRunStreams } from "@/lib/runStream";

import { renderThread, stubDesktop } from "./threadHelpers";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/r/4",
}));

const tick = (ms: number) => act(async () => {
  await vi.advanceTimersByTimeAsync(ms);
});

beforeEach(() => {
  vi.useFakeTimers();
  stubDesktop();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  resetRunStreams();
});

// M9-C6: active_run → Researching…, disabled send, refetch every 2 s; settles → stops and shows the result.
describe("Thread with an active run", () => {
  it("polls every 2 s while active_run is set, then stops and shows the reply and finding", async () => {
    const api = createMockClient({ activeRunPolls: 2 });
    const getResearch = vi.spyOn(api, "getResearch");
    const listFindings = vi.spyOn(api, "listFindings");
    renderThread(FIXTURE_ACTIVE_RUN_ID, api);
    await tick(0);

    expect(getResearch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent("Researching…");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    const messages = screen.getByRole("list", { name: "Messages" });
    expect(within(messages).queryAllByText(/logical qubits below the error threshold/)).toHaveLength(0);
    expect(screen.queryAllByTestId("finding")).toHaveLength(0);
    const findingsLoads = listFindings.mock.calls.length;

    await tick(1999);
    expect(getResearch).toHaveBeenCalledTimes(1);
    await tick(1);
    expect(getResearch).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent("Researching…");

    await tick(2000);
    expect(getResearch).toHaveBeenCalledTimes(3);
    expect(screen.queryByRole("status")).toBeNull();
    expect(within(messages).getByText(/logical qubits below the error threshold/)).toBeVisible();
    expect(listFindings.mock.calls.length).toBeGreaterThan(findingsLoads);
    expect(screen.getAllByTestId("finding")).toHaveLength(1);
    expect(screen.getByText(/Logical qubit error rates fall below/)).toBeVisible();

    await tick(10_000);
    expect(getResearch).toHaveBeenCalledTimes(3);
  });

  it("does not poll a thread without an active run", async () => {
    const api = createMockClient();
    const getResearch = vi.spyOn(api, "getResearch");
    renderThread(2, api);
    await tick(0);
    expect(screen.queryByRole("status")).toBeNull();
    await tick(10_000);
    expect(getResearch).toHaveBeenCalledTimes(1);
  });
});
