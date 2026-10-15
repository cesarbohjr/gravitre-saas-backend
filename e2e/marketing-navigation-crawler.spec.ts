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

// The cookie consent banner opens for every first-time visitor and its overlay
// intercepts clicks on footer links. Seed a stored decision so the crawler
// clicks the page itself.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "gravitre_marketing_consent_v1",
      JSON.stringify({
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
        analytics_storage: "denied",
        decidedAt: new Date().toISOString(),
      }),
    )
  })
})

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


test.describe("HeyCatch SEO and page structure regression", () => {
  test("homepage and about have exact rendered titles and one h1", async ({ page }) => {
    for (const [path, title] of [
      ["/", "Gravitre - One AI brain for your entire business"],
      ["/about", "About · Gravitre - One AI brain for your business"],
    ] as const) {
      await page.goto(path, { waitUntil: "networkidle" })
      await expect(page).toHaveTitle(title)
      await expect(page.locator("h1")).toHaveCount(1)
    }
  })

  test("features and pricing have one primary heading", async ({ page }) => {
    for (const path of ["/features", "/pricing"]) {
      await page.goto(path, { waitUntil: "domcontentloaded" })
      await expect(page.locator("h1")).toHaveCount(1)
    }
  })

  test("marketing sitemap and robots pointer are correct", async ({ request }) => {
    const sitemap = await request.get("/sitemap.xml")
    expect(sitemap.ok()).toBeTruthy()
    const xml = await sitemap.text()
    expect(xml).toContain("https://gravitre.app/pricing")
    expect(xml).toContain("https://gravitre.app/about")
    const robots = await request.get("/robots.txt")
    expect(robots.ok()).toBeTruthy()
    expect(await robots.text()).toContain("Sitemap: https://gravitre.app/sitemap.xml")
  })
})
