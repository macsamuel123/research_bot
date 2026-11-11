import { expect, test, type Page } from "@playwright/test";

import { expectNoHorizontalScroll, expectTouchTargets, screenshot } from "./helpers";

// M9-C6 (mock mode): Researching… + polling, 409 on send, and the streamed first turn from Landing.

const messages = (page: Page) => page.getByRole("list", { name: "Messages" });

test("an active run shows Researching…, disables Send, then shows the reply", async ({ page }, testInfo) => {
  await page.goto("/r/4");
  await expect(page.getByRole("heading", { level: 1, name: "Quantum error correction milestones" })).toBeVisible();
  const status = page.getByRole("status");
  await expect(status).toHaveText("Researching…");
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await page.getByRole("textbox", { name: "Message" }).fill("draft while busy");
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();

  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  await screenshot(page, testInfo, "thread-researching");

  // Fixture A settles after two 2 s polls: no reload needed.
  await expect(messages(page).getByText(/logical qubits below the error threshold/)).toBeVisible({ timeout: 20_000 });
  await expect(status).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();
});

test("a send while a watch run is active shows the 409 notice and keeps the draft", async ({ page }, testInfo) => {
  await page.goto("/r/5");
  await expect(page.getByRole("heading", { level: 1, name: "Heat pump subsidies" })).toBeVisible();
  const before = await messages(page).locator("[data-role]").count();
  const box = page.getByRole("textbox", { name: "Message" });
  await box.fill("Anything new on France?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveText("Still working on the previous answer");
  await expect(box).toHaveValue("Anything new on France?");
  await expect(messages(page).getByText("Anything new on France?")).toHaveCount(0);
  await expect(messages(page).locator("[data-role]")).toHaveCount(before);
  await expect(page.getByRole("status")).toHaveText("Researching…");
  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  await screenshot(page, testInfo, "thread-conflict");

  // The watch run settles and its message appears; the draft is still there to resend.
  await expect(messages(page).getByText(/one more country announced a subsidy change/)).toBeVisible({
    timeout: 20_000,
  });
  await expect(box).toHaveValue("Anything new on France?");
});

test("submitting a topic streams the first answer into the new thread", async ({ page }, testInfo) => {
  // Compile the thread route first so the dev server is not slower than the stream.
  await page.goto("/r/2");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.goto("/");
  const topic = "Grid-scale sodium-ion storage";
  await page.getByRole("textbox", { name: "Research topic" }).fill(topic);
  await page.getByRole("button", { name: "Research" }).click();
  await expect(page).toHaveURL(/\/r\/\d+$/);

  const streamingBubble = messages(page).locator("[data-streaming]");
  await expect(messages(page).getByText(topic)).toBeVisible();
  await expect(streamingBubble).toContainText("Looking into this");
  await expect(streamingBubble).not.toContainText("Research complete.");
  await expect(page.getByRole("status")).toHaveText("Researching…");
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await expectNoHorizontalScroll(page);
  await screenshot(page, testInfo, "thread-streaming");

  await expect(messages(page).getByText(/Research complete\.$/)).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0);
  await expect(streamingBubble).toHaveCount(0);

  // A follow-up streams the same way.
  await page.getByRole("textbox", { name: "Message" }).fill("And costs?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(messages(page).getByText("And costs?")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message" })).toHaveValue("");
  await expect(messages(page).locator("[data-role=assistant]").filter({ hasText: "Research complete." })).toHaveCount(2);
  await expectTouchTargets(page);
});
