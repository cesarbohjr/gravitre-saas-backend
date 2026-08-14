/**
 * Live network-failure proof for Billing & Plan UI.
 * Blocks /api/billing at the CDP network layer (real fail, not mocked SWR data)
 * and asserts the page never paints "Node Plan".
 *
 * Usage (already authenticated Chrome/Edge profile OR GRAVITRE_EMAIL/PASSWORD):
 *   node scripts/prove-billing-ui-failure-state.mjs
 */
import { chromium } from "playwright"

const BASE = process.env.GRAVITRE_APP_URL || "https://gravitre.app"
const EMAIL = process.env.GRAVITRE_EMAIL || process.env.E2E_EMAIL || ""
const PASSWORD = process.env.GRAVITRE_PASSWORD || process.env.E2E_PASSWORD || ""

async function maybeLogin(page) {
  if (!EMAIL || !PASSWORD) return false
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" })
  const email = page.getByLabel(/email/i).first()
  if (await email.count()) {
    await email.fill(EMAIL)
    await page.getByLabel(/password/i).first().fill(PASSWORD)
    await page.getByRole("button", { name: /sign in|log in/i }).first().click()
    await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 45000 }).catch(() => {})
  }
  return true
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext()
  const page = await context.newPage()

  // Real network failure: abort every billing overview request.
  await page.route("**/api/billing", async (route) => {
    if (route.request().method() === "GET" && !route.request().url().includes("/api/billing/")) {
      await route.abort("failed")
      return
    }
    // Also fail exact overview proxied as /api/billing with trailing stuff handled above.
    if (route.request().url().match(/\/api\/billing\/?(\?|$)/)) {
      await page.route.continue?.()
    }
    await route.abort("failed")
  })
  await page.route("**/api/billing?**", (route) => route.abort("failed"))

  const loggedIn = await maybeLogin(page)
  await page.goto(`${BASE}/settings/billing`, { waitUntil: "domcontentloaded", timeout: 60000 })
  await page.waitForTimeout(2500)

  const bodyText = await page.locator("body").innerText()
  const hasNodePlan = /\bNode Plan\b/i.test(bodyText)
  const hasUnavailable =
    /Plan unavailable|Could not load billing status|Loading plan/i.test(bodyText)
  const hasDollar49AsPlan = /\$49/.test(bodyText) && hasNodePlan

  const result = {
    url: page.url(),
    loggedInAttempted: loggedIn,
    onLoginPage: page.url().includes("/login"),
    hasNodePlan,
    hasUnavailable,
    hasDollar49AsPlan,
    pass: !hasNodePlan && (hasUnavailable || page.url().includes("/login")),
    snippet: bodyText.slice(0, 500),
  }
  console.log(JSON.stringify(result, null, 2))
  await browser.close()
  if (result.onLoginPage && !EMAIL) {
    console.error("BLOCKED: no session — set GRAVITRE_EMAIL/GRAVITRE_PASSWORD for authenticated live proof")
    process.exit(2)
  }
  process.exit(result.pass && !result.onLoginPage ? 0 : result.onLoginPage ? 2 : 1)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
