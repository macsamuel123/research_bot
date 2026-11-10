import { defineConfig, devices } from "@playwright/test";

// Mock-mode projects (desktop, mobile) run against a dev server started here with
// NEXT_PUBLIC_USE_MOCKS=1. The `stack` project runs against STACK_BASE_URL, which
// scripts/e2e-stack.sh starts (api with fake integrations + web through the Next proxy).
const MOCK_PORT = Number(process.env.E2E_MOCK_PORT ?? "3100");
const mockBaseUrl = `http://127.0.0.1:${MOCK_PORT}`;
const stackBaseUrl = process.env.STACK_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // The first hit on each route compiles it in the dev server.
  timeout: 90_000,
  expect: { timeout: 15_000 },
  forbidOnly: true,
  retries: 0,
  reporter: [["list"]],
  use: { trace: "retain-on-failure", timezoneId: "UTC", locale: "en-US" },
  projects: [
    {
      name: "desktop",
      testIgnore: /stack\//,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 }, baseURL: mockBaseUrl },
    },
    {
      name: "mobile",
      testIgnore: /stack\//,
      use: {
        ...devices["Pixel 7"],
        viewport: { width: 390, height: 844 },
        baseURL: mockBaseUrl,
      },
    },
    {
      name: "stack",
      testMatch: /stack\/.*\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: stackBaseUrl },
    },
  ],
  webServer: stackBaseUrl
    ? undefined
    : {
        command: `pnpm dev --hostname 127.0.0.1 --port ${MOCK_PORT}`,
        url: mockBaseUrl,
        env: { NEXT_PUBLIC_USE_MOCKS: "1" },
        reuseExistingServer: false,
        timeout: 120_000,
      },
});
