import { defineConfig, devices } from "@playwright/test";

const nodeExecutable = `"${process.execPath}"`;

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: "http://127.0.0.1:4174",
    trace: "on-first-retry",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 820 } } },
    { name: "narrow", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 820 } } },
  ],
  webServer: {
    command: `${nodeExecutable} ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4174`,
    url: "http://127.0.0.1:4174",
    reuseExistingServer: !process.env.CI,
  },
});

