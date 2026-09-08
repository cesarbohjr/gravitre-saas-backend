/**
 * Nodus product UI fidelity pack (P15).
 *
 * Fixed viewports from gate §25: 1280, 1440, 390.
 * Fixture shot harnesses (`/e2e/shots/*`) — no live customer data.
 *
 * Refresh baselines after accepted visual change:
 *   pnpm exec playwright test e2e/visual --update-snapshots
 *
 * Baselines: `e2e/visual/*-snapshots/` (committed when intentionally refreshed).
 * Do not invent product claims in fixtures.
 */
import { test, expect } from "@playwright/test"

const SURFACES = [
  { name: "home", path: "/e2e/shots/home" },
  { name: "agents", path: "/e2e/shots/agents" },
  { name: "workflows", path: "/e2e/shots/workflows" },
  { name: "approvals", path: "/e2e/shots/approvals" },
  { name: "connectors", path: "/e2e/shots/connectors" },
  { name: "activity", path: "/e2e/shots/activity" },
  { name: "builder", path: "/e2e/shots/builder" },
  { name: "ai", path: "/e2e/shots/ai" },
] as const

const VIEWPORTS = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1280", width: 1280, height: 800 },
  { name: "mobile-390", width: 390, height: 844 },
] as const

test.describe("Nodus product UI fidelity pack (P15)", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
  })

  for (const surface of SURFACES) {
    for (const viewport of VIEWPORTS) {
      test(`${surface.name} @ ${viewport.name}`, async ({ page }) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        await page.goto(surface.path, { waitUntil: "networkidle" })
        await page.waitForTimeout(400)
        await expect(page).toHaveScreenshot(`${surface.name}-${viewport.name}.png`, {
          animations: "disabled",
          caret: "hide",
          maxDiffPixelRatio: 0.02,
        })
      })
    }
  }
})
