import { defineConfig, devices } from "@playwright/test"
import { existsSync } from "node:fs"
import { join } from "node:path"
import { mergeE2eProcessEnv } from "./e2e/load-env"

const e2eEnv = mergeE2eProcessEnv()
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001"
const backendURL = (e2eEnv.FASTAPI_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "")

const backendCwd = join(process.cwd(), "backend")
const isWin = process.platform === "win32"
const venvPython = join(backendCwd, ".venv", isWin ? "Scripts" : "bin", isWin ? "python.exe" : "python")
const pythonCmd = existsSync(venvPython) ? venvPython : "python"

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  timeout: 180_000,
  expect: { timeout: 30_000 },
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${pythonCmd} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: "backend",
      url: `${backendURL}/health`,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
      env: {
        ...e2eEnv,
        APP_ENV: e2eEnv.APP_ENV ?? "dev",
        FASTAPI_BASE_URL: backendURL,
      },
    },
    {
      command: "pnpm dev --port 3001",
      cwd: "apps/web",
      url: baseURL,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 180_000,
      env: {
        ...e2eEnv,
        FASTAPI_BASE_URL: backendURL,
        PORT: "3001",
        NEXT_PUBLIC_PLAYWRIGHT_E2E: "1",
        PLAYWRIGHT_E2E: "1",
      },
    },
  ],
})
