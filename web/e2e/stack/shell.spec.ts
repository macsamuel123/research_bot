import { expect, test } from "@playwright/test";

// Stage 1 (mock UI) smoke for the full stack: the web app is served through the
// Next dev server with NEXT_PUBLIC_USE_MOCKS=0. The M7-C6 full-stack journey
// (watch + delete against FastAPI) lands with stage 2 once the researches API exists.
test("web app renders the landing page through the stack", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What do you want to research?" })).toBeVisible();
});
