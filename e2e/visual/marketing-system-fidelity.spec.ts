/**
 * Marketing System 4.0 — visual fidelity pack (frozen motion).
 *
 * Emulates prefers-reduced-motion + disables CSS/WAAPI animations so public
 * marketing pages can take stable first-viewport screenshots.
 *
 * Refresh baselines after accepted visual change:
 *   PLAYWRIGHT_REUSE_SERVER=1 pnpm exec playwright test -c playwright.visual.config.ts e2e/visual/marketing-system-fidelity.spec.ts --update-snapshots
 *
 * Baselines: e2e/visual/marketing-system-fidelity.spec.ts-snapshots/
 * No invented prices/claims in assertions — capture only.
 */
import { test, expect } from "@playwright/test"

const SURFACES = [
  { name: "home", path: "/" },
  { name: "pricing", path: "/pricing" },
  { name: "features", path: "/features" },
  { name: "technology", path: "/features/technology" },
  { name: "security", path: "/security" },
  { name: "roadmap", path: "/roadmap" },
] as const

const VIEWPORTS = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1280", width: 1280, height: 800 },
  { name: "mobile-390", width: 390, height: 844 },
] as const

test.describe("Marketing System 4.0 visual fidelity (frozen motion)", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
    await page.addInitScript(() => {
      const style = document.createElement("style")
      style.textContent = `
        *, *::before, *::after {
          animation: none !important;
          animation-duration: 0s !important;
          transition: none !important;
          scroll-behavior: auto !important;
        }
      `
      document.documentElement.appendChild(style)
    })
  })

  for (const surface of SURFACES) {
    for (const viewport of VIEWPORTS) {
      test(`${surface.name} @ ${viewport.name}`, async ({ page }) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        await page.goto(surface.path, { waitUntil: "networkidle" })
        // Settle fonts / lazy chunks after reduced-motion grid paints
        await page.waitForTimeout(500)
        await expect(page).toHaveScreenshot(`${surface.name}-${viewport.name}.png`, {
          animations: "disabled",
          caret: "hide",
          fullPage: false,
          maxDiffPixelRatio: 0.03,
        })
      })
    }
  }
})
