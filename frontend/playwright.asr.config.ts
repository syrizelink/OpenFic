import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

const dataDir = mkdtempSync(join(tmpdir(), "openfic-asr-e2e-"));

export default defineConfig({
  testDir: "./e2e",
  testMatch: "speech.spec.ts",
  workers: 1,
  fullyParallel: false,
  timeout: 90000,
  expect: { timeout: 15000 },
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:19000",
    viewport: { width: 1600, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
      args: [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
        ...(process.env.OPENFIC_ASR_SAMPLE
          ? [`--use-file-for-fake-audio-capture=${process.env.OPENFIC_ASR_SAMPLE}`]
          : []),
      ],
    },
  },
  webServer: [
    {
      command: "node e2e/asr-provider.mjs",
      url: "http://127.0.0.1:18888/health",
      timeout: 30000,
    },
    {
      command:
        "../backend/.venv/bin/python -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 18000 --log-level warning",
      env: { OPENFIC_DATA_DIR: dataDir, POSTHOG_API_KEY: "", LOGURU_LEVEL: "WARNING" },
      url: "http://127.0.0.1:18000/api/v1/health",
      timeout: 120000,
    },
    {
      command: "node_modules/.bin/vp dev --host 127.0.0.1 --port 19000",
      env: { VITE_BACKEND_URL: "http://127.0.0.1:18000" },
      url: "http://127.0.0.1:19000",
      timeout: 120000,
    },
  ],
});
