/**
 * UI 3.0 visual regression scaffold.
 *
 * Uses fixture shot harnesses (`/e2e/shots/*`) so goldens do not need a live
 * backend or customer data. Animations are frozen via prefers-reduced-motion.
 *
 * Generate / refresh baselines (after Phase 7 accept + stable local render):
 *   pnpm exec playwright test e2e/visual --update-snapshots
 *
 * Baselines live under `e2e/visual/ui-3-0-shots.spec.ts-snapshots/`.
 * Do not invent product claims in fixtures — shots already use operational fixtures.
 */
import { test, expect } from "@playwright/test"

const SURFACES = [
  { name: "agents", path: "/e2e/shots/agents" },
  { name: "workflows", path: "/e2e/shots/workflows" },
  { name: "approvals", path: "/e2e/shots/approvals" },
  { name: "connectors", path: "/e2e/shots/connectors" },
  { name: "activity", path: "/e2e/shots/activity" },
  { name: "builder", path: "/e2e/shots/builder" },
] as const

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 768, height: 1024 },
] as const

test.describe("UI 3.0 visual goldens (shot harness)", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
  })

  for (const surface of SURFACES) {
    for (const viewport of VIEWPORTS) {
      test(`${surface.name} @ ${viewport.name}`, async ({ page }) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        await page.goto(surface.path, { waitUntil: "networkidle" })
        // Settle fixture auth + first paint after reduced-motion.
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
