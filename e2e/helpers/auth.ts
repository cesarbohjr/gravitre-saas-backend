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

const WELCOME_DISMISSED_STORAGE_KEY = "gravitre-welcome-dismissed"

export async function skipOnboardingForOrg(page: Page, orgId: string) {
  try {
    await page.evaluate(async (selectedOrgId) => {
      const apiFetch = window.__gravitreApiFetch
      if (!apiFetch) {
        throw new Error("Playwright E2E helper missing: window.__gravitreApiFetch")
      }
      const response = await apiFetch("/api/onboarding/skip", {
        method: "POST",
        headers: { "x-org-id": selectedOrgId },
      })
      if (!response.ok) {
        const body = await response.text()
        throw new Error(`Failed to skip onboarding (${response.status}): ${body}`)
      }
    }, orgId)
  } catch {
    // Fixtures seed skipped onboarding; ignore transient proxy/backend failures here.
  }
}

export async function dismissOnboardingChecklistForOrg(page: Page) {
  try {
    await page.evaluate(async () => {
    const apiFetch = window.__gravitreApiFetch
    if (!apiFetch) {
      throw new Error("Playwright E2E helper missing: window.__gravitreApiFetch")
    }
    const settingsResponse = await apiFetch("/api/settings")
    if (!settingsResponse.ok) return
    const payload = (await settingsResponse.json()) as { settings?: Record<string, unknown> }
    const current = (payload.settings ?? {}) as Record<string, unknown>
    const onboarding = (current.onboarding ?? {}) as Record<string, unknown>
    if (onboarding.checklist_dismissed === true) return
    const nextSettings = {
      ...current,
      onboarding: {
        ...onboarding,
        checklist_dismissed: true,
      },
    }
    await apiFetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: nextSettings }),
    })
    })
  } catch {
    // Non-blocking — checklist overlay does not prevent sidebar navigation.
  }
}

/** Wait until AppShell exits the auth/billing bootstrap spinner and sidebar is interactive. */
export async function waitForAppShellReady(page: Page, timeout = 120_000) {
  await page
    .waitForResponse(
      (response) =>
        response.url().includes("/api/billing/status") && response.status() === 200,
      { timeout },
    )
    .catch(() => undefined)

  const bootSpinner = page.locator(
    "div.flex.h-screen.items-center.justify-center .animate-spin",
  )
  if (await bootSpinner.count()) {
    await bootSpinner.first().waitFor({ state: "hidden", timeout }).catch(() => undefined)
  }

  await page.locator("aside nav").waitFor({ state: "visible", timeout })
}

export async function prepareAdminAppSession(
  page: Page,
  user: BillingFixtureUser,
  landingPath = "/home",
) {
  await loginWithPassword(page, user.email, user.password)
  await setSelectedOrg(page, user.orgId)
  await clearTrialBannerDismiss(page)
  await page.evaluate((welcomeKey) => {
    window.localStorage.setItem(welcomeKey, "true")
    window.localStorage.removeItem("gravitre-nav-expanded")
  }, WELCOME_DISMISSED_STORAGE_KEY)

  await openProductPage(page, user.orgId, landingPath)
  await skipOnboardingForOrg(page, user.orgId)
  await dismissOnboardingChecklistForOrg(page)

  const sidebar = page.locator("aside nav")
  if (!(await sidebar.isVisible().catch(() => false))) {
    await waitForAppShellReady(page, 60_000)
  }

  const upgradeDismiss = page.getByRole("button", { name: "Not now" })
  if (await upgradeDismiss.isVisible().catch(() => false)) {
    await upgradeDismiss.click()
  }
}
