import { test, expect } from "@playwright/test"
import {
  loadBillingFixtures,
  loginWithPassword,
  openProductPage,
  type BillingFixtures,
} from "./helpers/auth"

let fixtures: BillingFixtures

test.beforeAll(() => {
  fixtures = loadBillingFixtures()
})

test.describe("Trial expiry billing flow", () => {
  test("expired trial: banner, 402 modal, billing navigation, custom checkout", async ({ page }) => {
    const user = fixtures.expiredTrial
    await loginWithPassword(page, user.email, user.password)
    const billingStatus = await openProductPage(page, user.orgId, "/assistant")
    expect(billingStatus.trialExpired).toBe(true)
    expect(billingStatus.canAccessApp).toBe(false)

    const expiredBanner = page.getByTestId("trial-expired-banner")
    await expect(expiredBanner).toBeVisible()
    await expect(expiredBanner).toContainText("Your 7-day trial has ended")
    await expect(page.getByTestId("active-trial-banner")).toHaveCount(0)
    await expect(expiredBanner.getByRole("button", { name: "Dismiss trial banner" })).toHaveCount(0)
    await expect(expiredBanner.locator('button[aria-label="Dismiss trial banner"]')).toHaveCount(0)

    await page.waitForLoadState("networkidle")
    const modal = page.getByTestId("upgrade-modal")
    if (await modal.isVisible()) {
      await page.getByRole("button", { name: "Not now" }).click()
      await expect(modal).not.toBeVisible()
    }

    const planRequiredResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/agent-jobs") &&
        response.request().method() === "POST" &&
        response.status() === 402,
    )

    const triggered402 = page.evaluate(async (orgId) => {
      const apiFetch = window.__gravitreApiFetch
      if (!apiFetch) {
        throw new Error("Playwright E2E helper missing: window.__gravitreApiFetch")
      }

      const response = await apiFetch("/api/agent-jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-org-id": orgId },
        body: JSON.stringify({ task: "e2e billing gate probe" }),
      })

      let body: Record<string, unknown> = {}
      try {
        body = (await response.json()) as Record<string, unknown>
      } catch {
        body = {}
      }

      const detail = (body.detail as Record<string, unknown> | undefined) ?? body
      return {
        status: response.status,
        error: detail.error,
        subscriptionStatus: detail.subscription_status,
      }
    }, user.orgId)

    const [response] = await Promise.all([planRequiredResponse, triggered402])
    const payload = await triggered402
    expect(response.status()).toBe(402)
    expect(payload.status).toBe(402)
    expect(payload.error).toBe("plan_required")
    expect(payload.subscriptionStatus).toBe("trial_expired")

    await expect(modal).toBeVisible({ timeout: 10_000 })
    await expect(modal.getByTestId("upgrade-modal-title")).toHaveText("Your trial has ended")

    for (const plan of ["node", "control", "command"] as const) {
      const card = modal.getByTestId(`upgrade-plan-${plan}`)
      await expect(card).toBeVisible()
      if (plan === "node") await expect(card).toContainText("$49/mo")
      if (plan === "control") await expect(card).toContainText("$129/mo")
      if (plan === "command") await expect(card).toContainText("$299/mo")
    }

    await modal.getByTestId("upgrade-plan-node").click()
    await expect(modal.getByTestId("upgrade-plan-node")).toHaveAttribute("aria-checked", "true")

    if (!process.env.STRIPE_SECRET_KEY) {
      test.info().annotations.push({
        type: "stripe",
        description: "STRIPE_SECRET_KEY not set — custom checkout page not exercised",
      })
      return
    }

    await Promise.all([
      page.waitForURL(/\/settings\/billing\/checkout\?plan=node/, { timeout: 60_000 }),
      modal.getByTestId("upgrade-continue-checkout").click(),
    ])

    await expect(page.getByTestId("payment-element-form")).toBeVisible({ timeout: 60_000 })
    await expect(page.getByRole("heading", { name: "Complete your subscription" })).toBeVisible()
  })

  test("canceled + expired trial: hard redirect, no expired-trial banner", async ({ page }) => {
    const user = fixtures.canceledWithExpiredTrial
    await loginWithPassword(page, user.email, user.password)
    const billingStatus = await openProductPage(page, user.orgId, "/assistant")
    expect(billingStatus.trialExpired).toBe(false)
    expect(billingStatus.billingState).toBe("canceled")
    await expect(page).toHaveURL(/\/settings\/billing/, { timeout: 60_000 })
    await expect(page.getByTestId("trial-expired-banner")).not.toBeVisible()
    await expect(page.getByTestId("active-trial-banner")).toHaveCount(0)
  })

  test("active trial: dismissible countdown banner, no expired banner", async ({ page }) => {
    const user = fixtures.activeTrial
    await loginWithPassword(page, user.email, user.password)
    const billingStatus = await openProductPage(page, user.orgId, "/assistant")
    expect(billingStatus.trialExpired).toBe(false)
    expect(billingStatus.billingStatus).toBe("trialing")

    await expect(page.getByTestId("active-trial-banner")).toBeVisible()
    await expect(page.getByTestId("active-trial-banner")).toContainText(
      "You're on a 7-day free trial of Node",
    )
    await expect(page.getByTestId("trial-expired-banner")).not.toBeVisible()
    await expect(
      page.getByTestId("active-trial-banner").getByRole("button", { name: "Dismiss trial banner" }),
    ).toBeVisible()
  })
})
