import { test, expect } from "@playwright/test"
import {
  loadBillingFixtures,
  loginWithPassword,
  setSelectedOrg,
  skipOnboardingForOrg,
  type BillingFixtures,
} from "./helpers/auth"

let fixtures: BillingFixtures

test.beforeAll(() => {
  fixtures = loadBillingFixtures()
})

test.describe("Billing overview network failure", () => {
  test("aborted /api/billing never paints Node Plan", async ({ page }) => {
    const user = fixtures.activeTrial
    await loginWithPassword(page, user.email, user.password)
    await setSelectedOrg(page, user.orgId)
    await skipOnboardingForOrg(page, user.orgId)

    // Real network failure at the route layer (not stubbed SWR data).
    // Match any host: BFF (/api/billing) or direct API. Never touch /billing/status.
    let abortedOverview = 0
    await page.route(/\/api\/billing\/?(\?|$)/, async (route) => {
      if (route.request().method() === "GET") {
        abortedOverview += 1
        await route.abort("failed")
        return
      }
      await route.continue()
    })

    await page.goto("/settings/billing", { waitUntil: "domcontentloaded" })
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 60_000 })
    await page.waitForTimeout(2000)

    const body = await page.locator("body").innerText()
    expect(abortedOverview, "overview GET must be aborted at least once").toBeGreaterThan(0)
    expect(body).not.toMatch(/\bNode Plan\b/i)
    expect(body).not.toMatch(/\$49\s*\/month/i)
    expect(body).toMatch(/Plan unavailable|Could not load billing status|Plan unknown|Loading plan/i)
  })
})
