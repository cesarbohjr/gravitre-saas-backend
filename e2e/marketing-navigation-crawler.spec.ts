import { test, expect } from "@playwright/test"

import {
  clickLinkAndVerify,
  crawlMarketingNavigation,
  formatNavigationReport,
} from "./helpers/navigation-crawler"
import {
  HUB_PAGES,
  HOMEPAGE_DEFAULT_TITLE,
  KNOWN_NAVIGATION_REGRESSIONS,
  METADATA_PAGES,
} from "./helpers/known-navigation-regressions"

const marketingOrigin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3000"

test.describe("Marketing navigation — known regressions", () => {
  for (const spec of KNOWN_NAVIGATION_REGRESSIONS) {
    test(`${spec.id}: click from ${spec.sourcePath}`, async ({ page }) => {
      await page.goto(spec.sourcePath, { waitUntil: "domcontentloaded" })
      const link = page.getByRole("link", { name: new RegExp(spec.linkText, "i") }).first()
      await expect(link).toBeVisible()

      const result = await clickLinkAndVerify({
        page,
        origin: marketingOrigin,
        sourcePath: spec.sourcePath,
        link: {
          href: (await link.getAttribute("href")) ?? "",
          text: spec.linkText,
          locator: link,
        },
        expectedPathPrefix: spec.expectedPathPrefix,
        minContentLength: 80,
      })

      expect(result.pass, `${spec.note}\n${formatNavigationReport([result])}`).toBe(true)
    })
  }
})

test.describe("Marketing navigation — page metadata", () => {
  for (const spec of METADATA_PAGES) {
    test(`${spec.path} has dedicated title`, async ({ page }) => {
      await page.goto(spec.path, { waitUntil: "domcontentloaded" })
      const title = await page.title()
      const ogTitle = await page.locator('meta[property="og:title"]').getAttribute("content")

      expect(title).not.toBe(HOMEPAGE_DEFAULT_TITLE)
      expect(title.toLowerCase()).toContain(spec.titleFragment.toLowerCase())
      if (ogTitle) {
        expect(ogTitle).not.toBe(HOMEPAGE_DEFAULT_TITLE)
        expect(ogTitle.toLowerCase()).toContain(spec.titleFragment.toLowerCase())
      }
    })
  }
})

test.describe("Marketing navigation — crawl and click", () => {
  test("header, footer, homepage CTAs, and hub card grids", async ({ page }) => {
    test.setTimeout(600_000)

    const homeResults = await crawlMarketingNavigation({
      page,
      origin: marketingOrigin,
      seedPaths: ["/"],
      maxHomeLinks: 22,
    })

    const hubResults = await crawlMarketingNavigation({
      page,
      origin: marketingOrigin,
      seedPaths: [...HUB_PAGES],
      maxHubLinksPerPage: 14,
    })

    const results = [...homeResults, ...hubResults]
    const report = formatNavigationReport(results)

    if (results.some((row) => !row.pass)) {
      await test.info().attach("navigation-crawl-report.txt", {
        body: report,
        contentType: "text/plain",
      })
    }

    expect(results.filter((row) => !row.pass), report).toHaveLength(0)
  })
})
