import { expect, test } from "@playwright/test";

// Smoke: the landing page renders through the Next dev server with NEXT_PUBLIC_USE_MOCKS=0.
test("web app renders the landing page through the stack", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What do you want to research?" })).toBeVisible();
});
