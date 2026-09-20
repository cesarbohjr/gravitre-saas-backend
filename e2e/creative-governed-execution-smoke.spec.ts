/**
 * Phase 7 — Governed Execution smoke on /security.
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

test.describe("Governed Execution — security smoke", () => {
  test("mounts with honesty caption", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.emulateMedia({ reducedMotion: "reduce" })
    const res = await page.goto(new URL("/security?govState=approval", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    expect(res?.ok() ?? false).toBe(true)

    const field = page.getByTestId("governed-execution-field")
    await expect(field).toBeVisible()
    const body = await page.locator("body").innerText()
    expect(body).toMatch(/Policy|Approval|Evidence/i)
    expect(body).toMatch(/Not a live compliance claim/i)
    await expect(page.getByTestId("gov-reduced")).toBeVisible()
  })

  test("govState=approval freezes waiting gate with path id", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(new URL("/security?govState=approval", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    const field = page.getByTestId("governed-execution-field")
    await expect(field).toHaveAttribute("data-creative-phase", "approval")
    await expect(field).toHaveAttribute("data-gov-waiting", "1")
    await expect(field).toHaveAttribute("data-gov-path-id", "path-gov-write")
    await expect(page.getByTestId("gov-waiting")).toBeVisible()
  })
})
