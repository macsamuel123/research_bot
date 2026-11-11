import { act, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createMockClient } from "@/lib/api/mock";
import { resetRunStreams } from "@/lib/runStream";

import { renderThread, stubDesktop } from "./threadHelpers";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/r/3",
}));

beforeEach(() => stubDesktop());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  resetRunStreams();
});

// Opening a thread never starts a run, so a capped or errored run is never retried (INV-9).
describe("Thread never auto-responds", () => {
  it("a pending user message with no active run makes zero respond calls", async () => {
    vi.useFakeTimers();
    const api = createMockClient();
    const respond = vi.spyOn(api, "respond");
    const sendMessage = vi.spyOn(api, "sendMessage");
    renderThread(3, api); // research 3: last message is the user's topic, no run
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText("State of Rust async runtimes beyond tokio", { selector: "li" })).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(respond).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled(); // blank draft only
  });

  it("after a stream error event and the refetch, no respond or extra send is issued", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    const respond = vi.spyOn(api, "respond");
    const getResearch = vi.spyOn(api, "getResearch");
    const sendMessage = vi.spyOn(api, "sendMessage").mockImplementation(async (_id, _content, handlers) => {
      handlers.onOpen?.();
      handlers.onEvent({ type: "token", text: "Partial" });
      handlers.onEvent({ type: "error", message: "The research stopped with an error" });
    });
    renderThread(3, api);
    const box = await screen.findByRole("textbox", { name: "Message" });
    fireEvent.change(box, { target: { value: "try again" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The research stopped with an error");
    await waitFor(() => expect(getResearch).toHaveBeenCalledTimes(2));
    await new Promise((r) => setTimeout(r, 50));
    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(respond).not.toHaveBeenCalled();
  });
});
