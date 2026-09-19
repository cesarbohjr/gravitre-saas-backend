/**
 * Pilot 3 — Entity Convergence width + kfState smoke (DOM, not pixel).
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

test.describe("Pilot 3 knowledge fabric — width + kfState smoke", () => {
  for (const width of WIDTHS) {
    test(`technology entity convergence mounts @ ${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 768 ? 844 : 900 })
      await page.emulateMedia({ reducedMotion: "reduce" })

      const url = new URL("/features/technology?kfState=match", origin).toString()
      const res = await page.goto(url, { waitUntil: "domcontentloaded" })
      expect(res?.ok() ?? false).toBe(true)

      const field = page.getByTestId("entity-convergence-field")
      await expect(field).toBeVisible()

      const body = await page.locator("body").innerText()
      expect(body).toMatch(/Entity Convergence|Mentions converge/i)
      expect(body).toMatch(/Not fuzzy person matching/i)
      expect(body).toMatch(/Not a live org graph/i)

      await expect(page.getByTestId("kf-reduced")).toBeVisible()
    })
  }

  test("kfState=match freezes exact convergence on desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    const url = new URL("/features/technology?kfState=match", origin).toString()
    await page.goto(url, { waitUntil: "domcontentloaded" })

    const field = page.getByTestId("entity-convergence-field")
    await expect(field).toHaveAttribute("data-creative-phase", "match")
    await expect(field).toHaveAttribute("data-kf-exact-converged", "1")
    await expect(field).toHaveAttribute("data-kf-fuzzy-merged", "0")
    await expect(page.getByTestId("kf-resolved-entity").first()).toBeVisible()
    await expect(page.getByTestId("kf-desktop")).toBeVisible()
  })

  test("kfState=reject_fuzzy keeps Sarah apart", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(new URL("/features/technology?kfState=reject_fuzzy", origin).toString(), {
      waitUntil: "domcontentloaded",
    })

    const field = page.getByTestId("entity-convergence-field")
    await expect(field).toHaveAttribute("data-creative-phase", "reject_fuzzy")
    await expect(field).toHaveAttribute("data-kf-fuzzy-merged", "0")
    await expect(page.getByTestId("kf-fuzzy-kept-apart")).toBeVisible()
    await expect(page.getByText("Sarah and Sarah Smith stay separate", { exact: false })).toBeVisible()
  })
})
