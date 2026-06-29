import fs from "node:fs"
import path from "node:path"
import type { Page } from "@playwright/test"

const FIXTURES_PATH = path.resolve(__dirname, "..", ".fixtures", "billing-users.json")

export type BillingFixtureUser = {
  orgId: string
  userId: string
  email: string
  password: string
}

export type BillingFixtures = {
  generatedAt: string
  expiredTrial: BillingFixtureUser
  activeTrial: BillingFixtureUser
  canceledWithExpiredTrial: BillingFixtureUser
}

export function loadBillingFixtures(): BillingFixtures {
  const raw = fs.readFileSync(FIXTURES_PATH, "utf-8")
  return JSON.parse(raw) as BillingFixtures
}

export async function loginWithPassword(page: Page, email: string, password: string) {
  await page.goto("/login?intent=login")
  await page.getByPlaceholder("you@company.com").fill(email)
  await page.getByPlaceholder("Enter your password").fill(password)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 90_000 })
}

export async function openProductPage(page: Page, orgId: string, path = "/assistant") {
  await setSelectedOrg(page, orgId)
  await clearTrialBannerDismiss(page)
  const billingStatus = page.waitForResponse(
    (response) => response.url().includes("/api/billing/status") && response.status() === 200,
  )
  await page.goto(path)
  const response = await billingStatus
  return (await response.json()) as Record<string, unknown>
}

const ORG_STORAGE_KEY = "gravitre:selectedOrg"

export async function setSelectedOrg(page: Page, orgId: string, orgName = "E2E Org") {
  await page.evaluate(
    ({ key, org }) => {
      window.localStorage.setItem(key, JSON.stringify(org))
    },
    { key: ORG_STORAGE_KEY, org: { id: orgId, name: orgName } },
  )
}

export async function clearTrialBannerDismiss(page: Page) {
  await page.evaluate(() => {
    window.sessionStorage.removeItem("gravitre-trial-banner-dismissed")
    window.sessionStorage.removeItem("gravitre-plan-required")
  })
}
