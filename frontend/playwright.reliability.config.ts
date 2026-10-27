import { defineConfig } from "@playwright/test";

import background from "./playwright.background.config";

export default defineConfig(background, {
  testMatch: "subagent-reliability.spec.ts",
  reporter: [["list"], ["html", { outputFolder: "playwright-report/reliability", open: "never" }]],
  outputDir: "test-results/reliability",
});
