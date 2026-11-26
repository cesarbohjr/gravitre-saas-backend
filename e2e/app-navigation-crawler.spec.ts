import { test, expect } from "@playwright/test"

import { ADMIN_APP_NAV_ITEMS } from "./helpers/app-navigation-items"
import {
  crawlAppSidebarNavigation,
  formatNavigationReport,
} from "./helpers/app-navigation-crawler"
import { loadBillingFixtures, prepareAdminAppSession } from "./helpers/auth"

const appOrigin =
  process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001"

const hasSupabaseCredentials = () => {
  const url = process.env.SUPABASE_URL ?? ""
  return (
    Boolean(url) &&
    !url.includes("test.supabase.co") &&
    !url.includes("placeholder")
  )
}

test.describe("Web app sidebar navigation — click-through crawl", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!hasSupabaseCredentials(), "Requires Supabase Actions secrets for billing fixture seed")
    test.setTimeout(1_800_000)
    const user = loadBillingFixtures().activeTrial
    await prepareAdminAppSession(page, user, "/home")
  })

  test("Agents to Assignments survives delayed roster preference hydration", async ({ page }) => {
    let release!: () => void
    const pending = new Promise<void>((resolve) => { release = resolve })
    let requested!: () => void
    const requestSeen = new Promise<void>((resolve) => { requested = resolve })
    await page.route("**/api/settings/agents-fleet*", async (route) => {
      if (route.request().method() !== "GET") return route.continue()
      requested()
      await pending
      await route.continue().catch(() => undefined)
    })
    try {
      await page.goto("/agents", { waitUntil: "domcontentloaded" })
      await requestSeen
      const link = page.locator('aside nav[aria-label="Primary"] a[href="/assignments"]')
      await expect(link).toBeVisible()
      await link.click()
      release()
      await expect(page).toHaveURL(/\/assignments(?:[?#].*)?$/)
      await expect(page.getByRole("heading", { name: "Assignments", exact: true })).toBeVisible()
      await expect(page).toHaveURL(/\/assignments(?:[?#].*)?$/)
    } finally {
      release()
      await page.unroute("**/api/settings/agents-fleet*")
    }
  })

  test("every admin sidebar item navigates via real click", async ({ page }) => {
    test.setTimeout(1_800_000)

    const results = await crawlAppSidebarNavigation({
      page,
      origin: appOrigin,
      items: ADMIN_APP_NAV_ITEMS,
      seedPath: "/home",
      startFromCurrentPage: true,
    })

    const report = formatNavigationReport(results)
    const failed = results.filter((row) => !row.pass)

    if (failed.length > 0) {
      await test.info().attach("app-navigation-crawl-report.txt", {
        body: report,
        contentType: "text/plain",
      })
    }

    expect(failed, report).toHaveLength(0)
  })
})
