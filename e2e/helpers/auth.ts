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
  founder?: BillingFixtureUser | null
  founderTrialCustomer?: BillingFixtureUser | null
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
  const pageErrors: string[] = []
  const recordError = (error: Error) => pageErrors.push(error.message)
  page.on("pageerror", recordError)
  await page.goto("/login?intent=login")
  // A cold Next dev server can expose SSR inputs before React attaches handlers.
  // Wait for the existing E2E AuthProvider effect before filling the real form.
  try {
    await page.waitForFunction(() => Boolean((window as Window & { __GRAVITRE_AUTH_TEST?: unknown }).__GRAVITRE_AUTH_TEST), undefined, { timeout: 30_000 })
  } catch {
    throw new Error(`Login did not hydrate: ${pageErrors.join("; ").slice(0, 2000)}`)
  } finally {
    page.off("pageerror", recordError)
  }
  await page.getByPlaceholder("you@company.com").fill(email)
  await page.getByPlaceholder("Enter your password").fill(password)
  // MarketingProviders performs a document reload when sign-in enters the app.
  // Wait for that bridge to finish before another protected-page navigation.
  const appDocumentReady = page.waitForEvent("domcontentloaded", { timeout: 90_000 })
    .then(() => true, () => false)
  const authenticated = page.waitForResponse(response => new URL(response.url()).pathname === "/auth/v1/token" && response.request().method() === "POST", { timeout: 30_000 })
  await page.getByRole("button", { name: "Sign in" }).click()
  const response = await authenticated.catch(async () => {
    throw new Error(`Supabase sign-in sent no completed token response: ${(await page.locator("body").innerText()).slice(-6000)}`)
  })
  if (!response.ok()) {
    const error = await response.json()
    throw new Error(`Supabase password sign-in failed (${response.status()}): ${error.error_code || error.code || "unknown"}`)
  }
  try {
    if (!await appDocumentReady) throw new Error("Post-login app document did not load")
    await page.waitForLoadState("load")
    await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 90_000 })
  } catch {
    // Text excludes password input values and auth response bodies/tokens.
    throw new Error(`Sign-in returned ${response.status()} but stayed at ${new URL(page.url()).pathname}: ${(await page.locator("body").innerText()).slice(-6000)}`)
  }
}

export async function openProductPage(page: Page, orgId: string, path = "/assistant") {
  await setSelectedOrg(page, orgId)
  await clearTrialBannerDismiss(page)
  await page.goto(path)
  await page.waitForFunction(() => Boolean(window.__gravitreApiFetch))
  // Read in the current document: CDP response handles can be invalidated by
  // the /assistant redirect before response.json() is consumed by the runner.
  return afterNavigationSettles(page, () => page.evaluate(async (selectedOrgId) => {
    const apiFetch = window.__gravitreApiFetch
    if (!apiFetch) throw new Error("Authenticated E2E helper required")
    const response = await apiFetch("/api/billing/status", { headers: { "x-org-id": selectedOrgId } })
    if (response.status !== 200) throw new Error(`Billing status returned ${response.status}`)
    return (await response.json()) as Record<string, unknown>
  }, orgId))
}

const ORG_STORAGE_KEY = "gravitre:selectedOrg"

/** Post-login client redirects can destroy the execution context mid-evaluate; settle and retry. */
async function afterNavigationSettles<T>(page: Page, run: () => Promise<T>, attempts = 4): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    await page.waitForLoadState("domcontentloaded").catch(() => undefined)
    try {
      return await run()
    } catch (error) {
      const destroyed = error instanceof Error && /Execution context was destroyed|navigation/i.test(error.message)
      if (!destroyed || attempt >= attempts) throw error
      await page.waitForTimeout(500 * attempt)
    }
  }
}

export async function setSelectedOrg(page: Page, orgId: string, orgName = "E2E Org") {
  await afterNavigationSettles(page, () =>
    page.evaluate(
      ({ key, org }) => {
        window.localStorage.setItem(key, JSON.stringify(org))
      },
      { key: ORG_STORAGE_KEY, org: { id: orgId, name: orgName } },
    ),
  )
}

export async function clearTrialBannerDismiss(page: Page) {
  await afterNavigationSettles(page, () =>
    page.evaluate(() => {
      window.sessionStorage.removeItem("gravitre-trial-banner-dismissed")
      window.sessionStorage.removeItem("gravitre-plan-required")
    }),
  )
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

  await page.locator('aside nav[aria-label="Primary"]').waitFor({ state: "visible", timeout })
}

export async function prepareAdminAppSession(
  page: Page,
  user: BillingFixtureUser,
  landingPath = "/home",
) {
  await loginWithPassword(page, user.email, user.password)
  await setSelectedOrg(page, user.orgId)
  await clearTrialBannerDismiss(page)
  await afterNavigationSettles(page, () =>
    page.evaluate((welcomeKey) => {
      window.localStorage.setItem(welcomeKey, "true")
      window.localStorage.removeItem("gravitre-nav-expanded")
    }, WELCOME_DISMISSED_STORAGE_KEY),
  )

  await openProductPage(page, user.orgId, landingPath)
  await skipOnboardingForOrg(page, user.orgId)
  await dismissOnboardingChecklistForOrg(page)

  const sidebar = page.locator('aside nav[aria-label="Primary"]')
  if (!(await sidebar.isVisible().catch(() => false))) {
    await waitForAppShellReady(page, 60_000)
  }

  const upgradeDismiss = page.getByRole("button", { name: "Not now" })
  if (await upgradeDismiss.isVisible().catch(() => false)) {
    await upgradeDismiss.click()
  }
}
