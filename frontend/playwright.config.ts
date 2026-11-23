import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 10 * 60 * 1000,
  expect: {
    timeout: 30 * 1000,
  },
  reporter: [["list"]],
  use: {
    baseURL: process.env.OPENFIC_E2E_BASE_URL ?? "http://127.0.0.1:9000",
    launchOptions: process.env.OPENFIC_E2E_CHROMIUM_PATH
      ? { executablePath: process.env.OPENFIC_E2E_CHROMIUM_PATH }
      : undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 30 * 1000,
    ...devices["Desktop Chrome"],
    viewport: { width: 1600, height: 1000 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
