import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Composer, CONFLICT_TEXT } from "@/components/Composer";
import { createMockClient, FIXTURE_CONFLICT_ID, MOCK_REPLY_CHUNKS } from "@/lib/api/mock";
import { resetRunStreams } from "@/lib/runStream";

import { renderThread, stubDesktop } from "./threadHelpers";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/r/5",
}));

beforeEach(() => stubDesktop());
afterEach(() => {
  vi.unstubAllGlobals();
  resetRunStreams();
});

describe("Composer", () => {
  it("keeps the draft and shows the conflict notice on 409; clears it on ok", async () => {
    const onSend = vi.fn<(c: string) => Promise<"ok" | "conflict" | "error">>().mockResolvedValueOnce("conflict");
    onSend.mockResolvedValueOnce("ok");
    render(<Composer disabled={false} onSend={onSend} />);
    const box = screen.getByRole("textbox", { name: "Message" });
    fireEvent.change(box, { target: { value: "follow-up" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(CONFLICT_TEXT);
    expect(box).toHaveValue("follow-up");
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(box).toHaveValue(""));
    expect(onSend).toHaveBeenCalledWith("follow-up");
  });

  it("disables Send while disabled or the draft is blank", () => {
    const { rerender } = render(<Composer disabled onSend={vi.fn()} />);
    const send = screen.getByRole("button", { name: "Send" });
    fireEvent.change(screen.getByRole("textbox", { name: "Message" }), { target: { value: "x" } });
    expect(send).toBeDisabled();
    rerender(<Composer disabled={false} onSend={vi.fn()} />);
    expect(send).toBeEnabled();
  });
});

// M9-C6: a 409 on send shows the notice, keeps the draft and adds no message.
describe("Thread send conflicts", () => {
  it("409 (watch run started) keeps the draft, adds no message, then shows Researching…", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    renderThread(FIXTURE_CONFLICT_ID, api);
    const list = await screen.findByRole("list", { name: "Messages" });
    const before = list.querySelectorAll("[data-role]").length;

    const box = screen.getByRole("textbox", { name: "Message" });
    fireEvent.change(box, { target: { value: "Anything new on France?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Still working on the previous answer");
    expect(box).toHaveValue("Anything new on France?");
    expect(within(list).queryByText("Anything new on France?")).toBeNull();
    expect(await screen.findByRole("status")).toHaveTextContent("Researching…");
    expect(list.querySelectorAll("[data-role]")).toHaveLength(before);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("an accepted send shows the user message, streams the reply and clears the draft", async () => {
    const api = createMockClient({ chunkDelayMs: 0 });
    renderThread(2, api);
    const list = await screen.findByRole("list", { name: "Messages" });
    const box = screen.getByRole("textbox", { name: "Message" });
    fireEvent.change(box, { target: { value: "What about yields?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await within(list).findByText("What about yields?")).toBeVisible();
    expect(box).toHaveValue("");
    await waitFor(() => expect(within(list).getByText(MOCK_REPLY_CHUNKS.join(""))).toBeVisible());
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    expect(list.querySelector("[data-streaming]")).toBeNull();
    expect(await screen.findByText(/Mock finding for/)).toBeVisible();
  });
});
