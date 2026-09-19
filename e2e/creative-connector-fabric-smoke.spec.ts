/**
 * Phase 7 — Connector Fabric smoke on /docs/integrations.
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

test.describe("Connector Fabric — docs integrations smoke", () => {
  test("mounts with honesty and capability ports", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.emulateMedia({ reducedMotion: "reduce" })
    const res = await page.goto(new URL("/docs/integrations?cfState=write_waiting", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    expect(res?.ok() ?? false).toBe(true)

    const field = page.getByTestId("connector-fabric-field")
    await expect(field).toBeVisible()
    const body = await page.locator("body").innerText()
    expect(body).toMatch(/capability ports|Connector fabric/i)
    expect(body).toMatch(/Not a live inventory/i)
    await expect(page.getByTestId("cf-reduced")).toBeVisible()
  })

  test("cfState=write_waiting freezes governed write", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(new URL("/docs/integrations?cfState=write_waiting", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    const field = page.getByTestId("connector-fabric-field")
    await expect(field).toHaveAttribute("data-creative-phase", "write_waiting")
    await expect(field).toHaveAttribute("data-cf-write-waiting", "1")
    await expect(field).toHaveAttribute("data-cf-logo-wall", "0")
    await expect(page.getByTestId("cf-waiting")).toBeVisible()
  })
})
