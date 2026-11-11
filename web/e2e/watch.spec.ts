import { expect, test, type Page } from "@playwright/test";

import {
  closePanel,
  closeSidebar,
  expectNoHorizontalScroll,
  expectTouchTargets,
  isMobile,
  openPanelTab,
  openSidebar,
  screenshot,
  sidebarItem,
} from "./helpers";

const TITLE = "Solid-state battery startups";

async function expectIndicator(page: Page, label: "watch on" | "watch off"): Promise<void> {
  const nav = await openSidebar(page);
  await expect(sidebarItem(nav, TITLE).getByRole("img", { name: /^watch (on|off)$/ })).toHaveAccessibleName(label);
  await closeSidebar(page);
}

// M7-C6, M7-C8
test("watch toggle, presets and pause update the sidebar indicator right away", async ({ page }, testInfo) => {
  await page.goto("/r/2");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await expectIndicator(page, "watch off");

  let panel = await openPanelTab(page, "Watch");
  const toggle = panel.getByRole("switch", { name: "Watch this research" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expect(panel.getByRole("button", { name: "Daily" })).toHaveAttribute("aria-pressed", "true");

  await expectNoHorizontalScroll(page);
  await expectTouchTargets(page);
  await screenshot(page, testInfo, "watch");

  if (isMobile(page)) await closePanel(page);
  await expectIndicator(page, "watch on");

  panel = await openPanelTab(page, "Watch");
  for (const preset of ["Every 6h", "Weekly"]) {
    await panel.getByRole("button", { name: preset }).click();
    await expect(panel.getByRole("button", { name: preset })).toHaveAttribute("aria-pressed", "true");
  }
  await expect(panel.getByRole("button", { name: "Daily" })).toHaveAttribute("aria-pressed", "false");

  await panel.getByRole("button", { name: "Pause watch" }).click();
  await expect(panel.getByTestId("watch-status")).toHaveText("Paused (was weekly)");
  await expect(panel.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  await closePanel(page);
  await expectIndicator(page, "watch off");
});

// M7-C6
test("delete opens a confirm dialog; cancel keeps, confirm deletes and goes home", async ({ page }, testInfo) => {
  await page.goto("/r/2");
  let panel = await openPanelTab(page, "Watch");

  await panel.getByRole("button", { name: "Delete research" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete this research?" });
  await expect(dialog).toBeVisible();
  await expectTouchTargets(page);
  await expectNoHorizontalScroll(page);
  await screenshot(page, testInfo, "watch-delete-confirm");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(/\/r\/2$/);
  await closePanel(page);
  let nav = await openSidebar(page);
  await expect(sidebarItem(nav, TITLE)).toBeVisible();
  await closeSidebar(page);

  panel = await openPanelTab(page, "Watch");
  await panel.getByRole("button", { name: "Delete research" }).click();
  await dialog.getByRole("button", { name: "Delete" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "What do you want to research?" })).toBeVisible();
  nav = await openSidebar(page);
  // Five fixtures (M9 adds the active-run and conflict threads), minus the deleted one.
  await expect(nav.getByTestId("sidebar-item")).toHaveCount(4);
  await expect(sidebarItem(nav, TITLE)).toHaveCount(0);
});
