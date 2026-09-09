/**
 * Marketing System 4.0 — DOM smoke goldens (not pixel diffs).
 *
 * Asserts key public routes render System 4.0 markers and authorized pricing
 * catalog amounts. Avoids toHaveScreenshot (motion/font flake).
 *
 * Run: pnpm exec playwright test e2e/marketing-system-smoke.spec.ts
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3000"

const ROUTES = [
  {
    path: "/",
    titleFragment: "gravitre",
    mustInclude: [/one ai brain|gravitre/i],
  },
  {
    path: "/pricing",
    titleFragment: "pricing",
    // Authorized PLAN_CATALOG amounts — regression guard, not invented
    mustInclude: [/\$59/, /\$149/, /\$349/, /Plan/i, /Role/i, /Outcome/i],
  },
  {
    path: "/features",
    titleFragment: "feature",
    mustInclude: [/Coordinate/i, /Approve/i, /Resolve/i],
  },
  {
    path: "/features/technology",
    titleFragment: "technolog",
    mustInclude: [/GIBE|knowledge|outcome/i],
  },
  {
    path: "/security",
    titleFragment: "secur",
    mustInclude: [/Identity|Encrypt|Approve|Audit/i],
  },
] as const

test.describe("Marketing System 4.0 — smoke goldens", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
  })

  for (const route of ROUTES) {
    test(`${route.path} renders System 4.0 markers`, async ({ page }) => {
      const res = await page.goto(new URL(route.path, origin).toString(), {
        waitUntil: "domcontentloaded",
      })
      expect(res?.ok() ?? false, `${route.path} should return OK`).toBe(true)

      const title = await page.title()
      expect(title.toLowerCase()).toContain(route.titleFragment.toLowerCase())

      const main = page.locator("main, [data-marketing-canvas], body")
      await expect(main.first()).toBeVisible()
      const text = await page.locator("body").innerText()
      expect(text.length).toBeGreaterThan(120)

      for (const pattern of route.mustInclude) {
        expect(text, `${route.path} missing ${pattern}`).toMatch(pattern)
      }
    })
  }

  test("auth routes use slim footer (no Product column)", async ({ page }) => {
    await page.goto(new URL("/login", origin).toString(), { waitUntil: "domcontentloaded" })
    const slim = page.locator('[data-marketing-footer="slim"]')
    await expect(slim).toBeVisible()
    await expect(page.locator('[data-marketing-footer="full"]')).toHaveCount(0)
    // Slim footer keeps legal links, not Product nav column
    await expect(slim.getByRole("link", { name: "Privacy" })).toBeVisible()
    await expect(slim.getByRole("navigation", { name: "Legal" }).getByRole("link", { name: "Features" })).toHaveCount(0)
  })
})
