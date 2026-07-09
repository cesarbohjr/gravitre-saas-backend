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
