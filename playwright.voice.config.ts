import { defineConfig, devices } from "@playwright/test"
import { mergeE2eProcessEnv } from "./e2e/load-env"

/**
 * Standing guard for the voice duplex capture regression (suspended AudioContext
 * starved the ScriptProcessor, so "listening" sent zero PCM).
 *
 * Deliberately separate from playwright.config.ts: the harness mocks the
 * Deepgram socket and every /api/voice fetch, so booting the FastAPI backend
 * would add a failure mode the guard is not meant to police.
 */

const e2eEnv = mergeE2eProcessEnv()
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3021"
const webPort = new URL(baseURL).port || "3021"

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/voice-duplex-browser.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  timeout: 120_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--autoplay-policy=user-gesture-required",
      ],
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // PLAYWRIGHT_REUSE_SERVER targets an already-running dev server; Next refuses a
  // second instance and probing the root route can outlast the boot timeout.
  webServer:
    process.env.PLAYWRIGHT_REUSE_SERVER === "1"
      ? undefined
      : [
          {
            command: `pnpm dev --port ${webPort}`,
            cwd: "apps/web",
            url: `${baseURL}/e2e/voice-duplex`,
            timeout: 300_000,
            env: {
              ...e2eEnv,
              PORT: webPort,
              NEXT_PUBLIC_PLAYWRIGHT_E2E: "1",
              PLAYWRIGHT_E2E: "1",
            },
          },
        ],
})
