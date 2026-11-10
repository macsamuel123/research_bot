import { expect, test } from "@playwright/test";

import { expectNoHorizontalScroll, expectTouchTargets, isMobile, openPanelTab, screenshot } from "./helpers";

// M7-C5, M7-C8
test("findings panel: title, summary, safe source link and dismiss", async ({ page }, testInfo) => {
  await page.goto("/r/1");
  await expect(page.getByRole("heading", { level: 1, name: "EU AI Act enforcement" })).toBeVisible();

  if (isMobile(page)) {
    // Mobile: no side panel until Details opens the bottom sheet.
    await expect(page.getByRole("complementary", { name: "Research details" })).toHaveCount(0);
  } else {
    // Desktop: side panel visible without any tap.
    await expect(page.getByRole("complementary", { name: "Research details" })).toBeVisible();
  }

  const panel = await openPanelTab(page, "Findings");
  const items = panel.getByTestId("finding");
  await expect(items).toHaveCount(4);

  const first = items.first();
  await expect(first.getByRole("heading")).toHaveText(/AI Office opens first formal inquiry/);
  await expect(first).toContainText("The AI Office requested technical documentation");
  const link = first.getByRole("link", { name: "digital-strategy.example.eu" });
  await expect(link).toHaveAttribute("href", "https://digital-strategy.example.eu/news/ai-office-first-inquiry");
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");

  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  await screenshot(page, testInfo, "findings");

  await panel.getByRole("button", { name: /Dismiss: Germany designates/ }).click();
  await expect(items).toHaveCount(3);
  await expect(panel.getByText(/Germany designates/)).toHaveCount(0);
});
