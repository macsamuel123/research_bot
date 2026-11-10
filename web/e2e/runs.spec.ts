import { expect, test } from "@playwright/test";

import { expectNoHorizontalScroll, expectTouchTargets, openPanelTab, screenshot } from "./helpers";

// M7-C7, M7-C8
test("run history: time, status badge, cost and new findings", async ({ page }, testInfo) => {
  await page.goto("/r/1");
  const panel = await openPanelTab(page, "Runs");
  const rows = panel.getByTestId("run");
  await expect(rows).toHaveCount(5);

  for (const status of ["running", "ok", "capped", "error"]) {
    await expect(panel.locator(`[data-status="${status}"]`).first()).toHaveText(status);
  }
  await expect(rows.getByTestId("run-cost")).toHaveText(["$0.00", "$12.34", "$0.50", "$0.05", "$0.00"]);
  await expect(rows.getByTestId("run-new")).toHaveText(["0 new", "3 new", "1 new", "0 new", "0 new"]);
  // timezoneId is UTC in playwright.config.ts.
  await expect(rows.nth(1).locator("time")).toHaveText("Nov 10, 08:00");

  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  await screenshot(page, testInfo, "runs");
});
