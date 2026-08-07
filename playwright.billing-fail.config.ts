import { defineConfig, devices } from "@playwright/test"
import { mergeE2eProcessEnv } from "./e2e/load-env"

mergeE2eProcessEnv()

/** Prod/live config with no local webServer — for network-abort proofs against gravitre.app */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/billing-overview-failure-no-node-default.spec.ts",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  timeout: 180_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "https://gravitre.app",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
})
