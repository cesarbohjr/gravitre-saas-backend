/**
 * Consume e2e/.fixtures/magic-link.txt and write gravitre-e2e-storage.json.
 *
 * Expects a URL that can establish a session:
 * - https://gravitre.app/auth/callback?token_hash=...&type=magiclink&next=/ai
 * - or an action_link whose redirect_to is /auth/callback (not a protected /ai)
 *
 * Do not point redirect_to at /ai: proxy auth-gates that path and drops the hash.
 */
import fs from "node:fs"
import { chromium } from "@playwright/test"

const linkPath = new URL("./.fixtures/magic-link.txt", import.meta.url)
const storagePath = new URL("./.fixtures/gravitre-e2e-storage.json", import.meta.url)

const link = fs.readFileSync(linkPath, "utf8").trim()
if (!link) {
  console.error("magic-link.txt is empty")
  process.exit(2)
}

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext()
const page = await context.newPage()

await page.goto(link, { waitUntil: "domcontentloaded", timeout: 90000 })

// Server verifyOtp redirects to /ai; hash handoff lands on /auth/callback/complete then /ai.
await page
  .waitForURL(
    (url) => {
      const u = typeof url === "string" ? new URL(url) : url
      return (
        u.hostname.endsWith("gravitre.app") &&
        (u.pathname === "/ai" ||
          u.pathname.startsWith("/ai/") ||
          u.pathname.startsWith("/home") ||
          u.pathname.startsWith("/welcome"))
      )
    },
    { timeout: 90000 },
  )
  .catch(() => {})

// Give cookie + localStorage session a moment to settle after setSession.
await page.waitForTimeout(2500)

const landed = new URL(page.url())
const state = await context.storageState()
const hasLocalSession = (state.origins || []).some((origin) =>
  (origin.localStorage || []).some((item) =>
    /supabase|sb-|access_token/i.test(item.name),
  ),
)
const hasCookieSession = (state.cookies || []).some(
  (c) =>
    (c.name.startsWith("sb-") || c.name.includes("auth-token")) &&
    Boolean(c.value) &&
    c.value.length > 20,
)
const hasSession = hasLocalSession || hasCookieSession

fs.writeFileSync(storagePath, JSON.stringify(state, null, 2))
if (fs.existsSync(linkPath)) {
  fs.unlinkSync(linkPath)
}

console.log(
  JSON.stringify({
    host: landed.host,
    path: landed.pathname,
    cookieCount: (state.cookies || []).length,
    originCount: (state.origins || []).length,
    hasLocalSession,
    hasCookieSession,
    hasSession,
  }),
)

await browser.close()
process.exit(hasSession ? 0 : 1)
