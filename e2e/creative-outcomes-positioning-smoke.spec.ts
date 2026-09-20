/**
 * Phase 10 — Outcomes Positioning smoke on /pricing.
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

test.describe("Outcomes Positioning — pricing smoke", () => {
  test("mounts with honesty caption and no invented metrics", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.emulateMedia({ reducedMotion: "reduce" })
    const res = await page.goto(new URL("/pricing?outcomesState=categories", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    expect(res?.ok() ?? false).toBe(true)

    const field = page.getByTestId("outcomes-positioning-field")
    await expect(field).toBeVisible()
    const body = await page.locator("body").innerText()
    expect(body).toMatch(/Revenue|Retention|Efficiency/i)
    expect(body).toMatch(/No invented metrics/i)
    // Must not invent ROI theater in the creative field
    const fieldText = await field.innerText()
    expect(fieldText).not.toMatch(/\$\d|%\s*(lift|increase|ROI)/i)
    await expect(page.getByTestId("outcomes-reduced")).toBeVisible()
  })

  test("outcomesState=categories freezes with collapse path id", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(new URL("/pricing?outcomesState=categories", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    const field = page.getByTestId("outcomes-positioning-field")
    await expect(field).toHaveAttribute("data-creative-phase", "categories")
    await expect(field).toHaveAttribute("data-outcomes-path-id", "path-outcomes-collapse")
    await expect(page.getByTestId("outcomes-categories")).toBeVisible()
  })
})
