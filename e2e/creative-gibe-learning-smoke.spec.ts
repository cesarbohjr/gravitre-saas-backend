/**
 * Phase 8 — GIBE Learning Loop smoke on /features/technology.
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

test.describe("GIBE Learning Loop — technology smoke", () => {
  test("mounts with honesty caption", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.emulateMedia({ reducedMotion: "reduce" })
    const res = await page.goto(new URL("/features/technology?gibeState=approve", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    expect(res?.ok() ?? false).toBe(true)

    const field = page.getByTestId("gibe-learning-field")
    await expect(field).toBeVisible()
    const body = await page.locator("body").innerText()
    expect(body).toMatch(/Observe|Recommend|Approve/i)
    expect(body).toMatch(/Not auto policy rewrite/i)
    await expect(page.getByTestId("gibe-reduced")).toBeVisible()
  })

  test("gibeState=approve freezes waiting gate with path id", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(new URL("/features/technology?gibeState=approve", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    const field = page.getByTestId("gibe-learning-field")
    await expect(field).toHaveAttribute("data-creative-phase", "approve")
    await expect(field).toHaveAttribute("data-gibe-waiting", "1")
    await expect(field).toHaveAttribute("data-gibe-path-id", "path-gibe-prefer")
    await expect(page.getByTestId("gibe-waiting")).toBeVisible()
  })
})
