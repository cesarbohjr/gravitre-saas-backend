import { defineConfig, devices } from "@playwright/test"

/**
 * Visual fidelity only — fixture shots patch fetch; no FastAPI required.
 * Usage:
 *   PLAYWRIGHT_REUSE_SERVER=1 pnpm exec playwright test -c playwright.visual.config.ts e2e/visual --update-snapshots
 */
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001"
const webPort = new URL(baseURL).port || "3001"

export default defineConfig({
  testDir: "./e2e/visual",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  timeout: 120_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `pnpm dev --port ${webPort}`,
    cwd: "apps/web",
    url: baseURL,
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 180_000,
    env: {
      ...process.env,
      PORT: webPort,
      NEXT_PUBLIC_PLAYWRIGHT_E2E: "1",
      PLAYWRIGHT_E2E: "1",
      E2E_SKIP_FIXTURE_SEED: "1",
    },
  },
})
