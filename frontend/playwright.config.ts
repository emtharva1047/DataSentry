import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const frontendDir = process.cwd();
const backendDir = path.resolve(frontendDir, "../backend");
const isolatedDataDir = path.join(backendDir, ".e2e-data");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI
    ? [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]]
    : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: backendDir,
      env: { PYTHONPATH: backendDir, DATASENTRY_DATA_DIR: isolatedDataDir },
      url: "http://127.0.0.1:8000/api/health",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run start -- --hostname 127.0.0.1",
      cwd: frontendDir,
      env: { NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000" },
      url: "http://127.0.0.1:3000",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
