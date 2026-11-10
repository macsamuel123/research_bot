import { expect, test, type Page } from "@playwright/test";

import { openPanelTab, openSidebar, sidebarItem } from "../helpers";

// M7-C6 full stack: web → Next proxy → FastAPI → Postgres (INTEGRATIONS_MODE=fake).
const password = process.env.E2E_OWNER_PASSWORD ?? "";

async function expectIndicator(page: Page, title: string, label: "watch on" | "watch off") {
  const nav = await openSidebar(page);
  await expect(sidebarItem(nav, title).getByRole("img", { name: /^watch (on|off)$/ })).toHaveAccessibleName(label);
}

test("watch toggle, presets, pause and delete work against the real API", async ({ page }) => {
  expect(password, "E2E_OWNER_PASSWORD is set by scripts/e2e-stack.sh").not.toBe("");
  const login = await page.request.post("/api/auth/login", { data: { password } });
  expect(login.status()).toBe(204);

  const title = `M7 stack watch ${Date.now()}`;
  await page.goto("/");
  await page.getByRole("textbox", { name: "Research topic" }).fill(title);
  await page.getByRole("button", { name: "Research" }).click();
  await expect(page).toHaveURL(/\/r\/\d+$/);
  const id = Number(new URL(page.url()).pathname.split("/").pop());
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  await expectIndicator(page, title, "watch off");

  // Enable: the sidebar indicator flips right away and the API stored daily.
  let panel = await openPanelTab(page, "Watch");
  const toggle = panel.getByRole("switch", { name: "Watch this research" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expectIndicator(page, title, "watch on");
  await expect(panel.getByRole("button", { name: "Daily" })).toHaveAttribute("aria-pressed", "true");

  // Weekly preset, then pause.
  await panel.getByRole("button", { name: "Weekly" }).click();
  await expect(panel.getByRole("button", { name: "Weekly" })).toHaveAttribute("aria-pressed", "true");
  await expect(panel.getByTestId("watch-status")).toHaveText("Watching weekly");
  await panel.getByRole("button", { name: "Pause watch" }).click();
  await expect(panel.getByTestId("watch-status")).toHaveText("Paused (was weekly)");
  await expectIndicator(page, title, "watch off");

  // The state is persisted server-side.
  await expect
    .poll(async () => {
      const detail = (await (await page.request.get(`/api/researches/${id}`)).json()) as {
        watch_enabled: boolean;
        schedule: string | null;
      };
      return [detail.watch_enabled, detail.schedule];
    })
    .toEqual([false, "weekly"]);
  await page.reload();
  panel = await openPanelTab(page, "Watch");
  await expect(panel.getByTestId("watch-status")).toHaveText("Paused (was weekly)");
  await expect(panel.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  await expectIndicator(page, title, "watch off");

  // Delete → Cancel keeps the research.
  await panel.getByRole("button", { name: "Delete research" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete this research?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`/r/${id}$`));
  expect((await page.request.get(`/api/researches/${id}`)).status()).toBe(200);

  // Delete → Confirm removes it, goes home and drops it from the sidebar.
  await panel.getByRole("button", { name: "Delete research" }).click();
  await dialog.getByRole("button", { name: "Delete" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "What do you want to research?" })).toBeVisible();
  const nav = await openSidebar(page);
  await expect(sidebarItem(nav, title)).toHaveCount(0);
  expect((await page.request.get(`/api/researches/${id}`)).status()).toBe(404);

  await page.reload();
  await expect(sidebarItem(await openSidebar(page), title)).toHaveCount(0);
});

test("owner API refuses requests without a session", async ({ playwright, baseURL }) => {
  const anon = await playwright.request.newContext({ baseURL });
  expect((await anon.get("/api/researches")).status()).toBe(401);
  await anon.dispose();
});
