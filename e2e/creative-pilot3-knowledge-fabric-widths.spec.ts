/**
 * Technology page — Entity Convergence Workbench width smoke (DOM, not pixel).
 *
 * The page mounts the KF-A workbench (see creative-experience-system.test.ts);
 * the older kfState-frozen EntityConvergenceField is no longer on this route.
 *
 * Run:
 *   PLAYWRIGHT_SKIP_BACKEND=1 PLAYWRIGHT_REUSE_SERVER=1 \
 *     pnpm exec playwright test e2e/creative-pilot3-knowledge-fabric-widths.spec.ts
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

const WIDTHS = [390, 430, 768, 1024, 1280, 1440, 1728] as const

test.describe("Technology entity convergence workbench — width smoke", () => {
  for (const width of WIDTHS) {
    test(`entity convergence workbench mounts @ ${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 768 ? 844 : 900 })
      await page.emulateMedia({ reducedMotion: "reduce" })

      const res = await page.goto(new URL("/features/technology", origin).toString(), {
        waitUntil: "domcontentloaded",
      })
      expect(res?.ok() ?? false).toBe(true)

      const workbench = page.getByTestId("entity-convergence-workbench")
      await expect(workbench).toBeVisible()
      await expect(page.getByTestId("kf-a-field")).toBeVisible()

      const body = await page.locator("body").innerText()
      expect(body).toMatch(/Mentions converge when the match is exact/i)
      expect(body).toMatch(/Not fuzzy person matching/i)
      expect(body).toMatch(/Not a live org graph/i)
    })
  }
})
