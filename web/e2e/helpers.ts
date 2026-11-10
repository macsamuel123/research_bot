import path from "node:path";

import { expect, type Locator, type Page, type TestInfo } from "@playwright/test";

export const isMobile = (page: Page): boolean => (page.viewportSize()?.width ?? 1280) < 1024;

/** INV-15: no horizontal scroll at the current viewport. */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(scrollWidth, "document scrolls horizontally").toBeLessThanOrEqual(innerWidth);
}

/** INV-15: every visible interactive element is at least 44px tall. */
export async function expectTouchTargets(page: Page): Promise<void> {
  const small = await page.evaluate(() => {
    const selector = "button, a[href], input, select, textarea, [role=switch], [role=tab]";
    return Array.from(document.querySelectorAll<HTMLElement>(selector))
      .filter((el) => {
        const r = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && style.visibility !== "hidden" && style.display !== "none";
      })
      .map((el) => ({
        text: (el.getAttribute("aria-label") ?? el.textContent ?? el.tagName).trim().slice(0, 40),
        height: Math.round(el.getBoundingClientRect().height * 10) / 10,
      }))
      .filter((x) => x.height < 44);
  });
  expect(small, "touch targets under 44px").toEqual([]);
}

export async function screenshot(page: Page, testInfo: TestInfo, screen: string): Promise<void> {
  await page.screenshot({
    path: path.join(__dirname, "..", "screenshots", `${screen}-${testInfo.project.name}.png`),
  });
}

/** Opens the Findings/Watch/Runs panel: side panel on desktop, bottom sheet on mobile. */
export async function openPanelTab(page: Page, tab: "Findings" | "Watch" | "Runs"): Promise<Locator> {
  let panel: Locator;
  if (isMobile(page)) {
    await page.getByRole("button", { name: "Details" }).click();
    panel = page.getByRole("dialog", { name: "Research details" });
  } else {
    panel = page.getByRole("complementary", { name: "Research details" });
  }
  await expect(panel).toBeVisible();
  await panel.getByRole("tab", { name: tab }).click();
  await expect(panel.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
  return panel;
}

export async function closePanel(page: Page): Promise<void> {
  if (isMobile(page)) {
    await page.getByRole("dialog", { name: "Research details" }).getByRole("button", { name: "Close" }).click();
  }
}

/** The sidebar navigation, opening the mobile drawer if needed. */
export async function openSidebar(page: Page): Promise<Locator> {
  if (isMobile(page)) await page.getByRole("button", { name: "Open menu" }).click();
  const nav = page.getByRole("navigation", { name: "Researches" });
  await expect(nav).toBeVisible();
  return nav;
}

export async function closeSidebar(page: Page): Promise<void> {
  if (!isMobile(page)) return;
  // Tap the visible strip of backdrop to the right of the drawer.
  const width = page.viewportSize()?.width ?? 390;
  await page.getByRole("button", { name: "Close menu" }).click({ position: { x: width - 12, y: 200 } });
  await expect(page.getByRole("button", { name: "Close menu" })).toHaveCount(0);
}

export function sidebarItem(nav: Locator, title: string): Locator {
  return nav.getByRole("link", { name: new RegExp(`^${title}`) });
}
