/**
 * click-audit.js
 *
 * Playwright crawl of marketing + authenticated web-app nav.
 *
 * Usage:
 *   node scripts/click-audit.js marketing https://gravitre.app
 *   node scripts/click-audit.js app https://gravitre.app --email you@x.com --password '...'
 *   node scripts/click-audit.js both https://gravitre.app --email you@x.com --password '...'
 *
 * Env fallbacks for app auth:
 *   CLICK_AUDIT_EMAIL / CLICK_AUDIT_PASSWORD
 */

const { chromium } = require("playwright")
const fs = require("node:fs")
const path = require("node:path")

const mode = process.argv[2] || "marketing"
const START_URL = process.argv[3] || "https://gravitre.app"

function argValue(flag) {
  const idx = process.argv.indexOf(flag)
  return idx >= 0 ? process.argv[idx + 1] : undefined
}

const EMAIL = argValue("--email") || process.env.CLICK_AUDIT_EMAIL || ""
const PASSWORD = argValue("--password") || process.env.CLICK_AUDIT_PASSWORD || ""
const HEADLESS = process.env.CLICK_AUDIT_HEADED !== "1"

const MARKETING_SELECTORS = [
  'header nav a[href]',
  'header a[href]',
  'footer a[href]',
]

const APP_SIDEBAR_SELECTOR = 'aside nav a[href]'

function normalizePath(url) {
  try {
    const u = new URL(url)
    return (u.pathname.replace(/\/+$/, "") || "/") + u.search + u.hash
  } catch {
    return url
  }
}

function sameOrigin(a, b) {
  try {
    return new URL(a).origin === new URL(b).origin
  } catch {
    return false
  }
}

async function collectCandidates(page, selectors, { requireVisible = true } = {}) {
  const selector = Array.isArray(selectors) ? selectors.join(", ") : selectors
  const locs = page.locator(selector)
  const count = await locs.count()
  const items = []
  const seen = new Set()

  for (let i = 0; i < count; i++) {
    const loc = locs.nth(i)
    if (requireVisible && !(await loc.isVisible().catch(() => false))) continue

    const meta = await loc.evaluate((el) => {
      const href = el.getAttribute("href")
      const text = (el.innerText || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ")
      const testId = el.getAttribute("data-testid") || ""
      const tag = el.tagName.toLowerCase()
      const rect = el.getBoundingClientRect()
      const topEl = document.elementFromPoint(rect.left + Math.min(rect.width / 2, 8), rect.top + Math.min(rect.height / 2, 8))
      const blockedBy =
        topEl && !el.contains(topEl) && topEl !== el
          ? {
              tag: topEl.tagName.toLowerCase(),
              className: String(topEl.className || "").slice(0, 120),
              id: topEl.id || "",
            }
          : null
      return {
        href,
        text: text.slice(0, 60),
        testId,
        tag,
        pointerEvents: getComputedStyle(el).pointerEvents,
        bodyPointerEvents: getComputedStyle(document.body).pointerEvents,
        blockedBy,
      }
    })

    if (!meta.href || meta.href.startsWith("mailto:") || meta.href.startsWith("tel:")) continue
    if (meta.href.startsWith("http") && !sameOrigin(meta.href, page.url()) && !meta.href.includes("gravitre")) {
      // keep external gravitre links; skip unrelated
    }

    const key = `${meta.href}::${meta.text}::${meta.testId}`
    if (seen.has(key)) continue
    seen.add(key)
    items.push({ index: i, ...meta, selector })
  }
  return items
}

async function clickAndObserve(page, item, { waitMs = 1200 } = {}) {
  const beforeUrl = page.url()
  const beforePath = normalizePath(beforeUrl)
  const consoleErrors = []
  const failedRequests = []
  const onConsole = (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text())
  }
  const onFailed = (req) => {
    failedRequests.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText || "failed"}`)
  }
  page.on("console", onConsole)
  page.on("requestfailed", onFailed)

  let clickError = null
  let hitTarget = null
  try {
    const loc = page.locator(item.selector).nth(item.index)
    await loc.scrollIntoViewIfNeeded().catch(() => undefined)

    hitTarget = await loc.evaluate((el) => {
      const rect = el.getBoundingClientRect()
      const x = rect.left + Math.min(Math.max(rect.width / 2, 2), 12)
      const y = rect.top + Math.min(Math.max(rect.height / 2, 2), 12)
      const top = document.elementFromPoint(x, y)
      return {
        x,
        y,
        expectedText: (el.innerText || "").trim().slice(0, 40),
        topTag: top?.tagName?.toLowerCase() || null,
        topClass: String(top?.className || "").slice(0, 160),
        topText: (top?.innerText || "").trim().slice(0, 40),
        isSelfOrChild: !!(top && (el === top || el.contains(top))),
        bodyPointerEvents: getComputedStyle(document.body).pointerEvents,
        htmlPointerEvents: getComputedStyle(document.documentElement).pointerEvents,
        scrollLocked: document.body.hasAttribute("data-scroll-locked"),
        ariaHiddenBody: document.body.getAttribute("aria-hidden"),
      }
    })

    await loc.click({ timeout: 8_000, force: false })
    await page.waitForTimeout(waitMs)
  } catch (err) {
    clickError = err instanceof Error ? err.message : String(err)
  } finally {
    page.off("console", onConsole)
    page.off("requestfailed", onFailed)
  }

  const afterUrl = page.url()
  const afterPath = normalizePath(afterUrl)
  const navigated = afterPath !== beforePath
  const expectedPath = item.href
    ? normalizePath(new URL(item.href, beforeUrl).href)
    : null

  let status = "OK"
  let reason = undefined
  if (clickError) {
    status = "FAIL"
    reason = `click error: ${clickError}`
  } else if (!navigated) {
    // Same-page hash or already-active link can be OK
    if (expectedPath && expectedPath === beforePath) {
      status = "OK"
      reason = "already on target"
    } else if (item.href?.startsWith("#")) {
      status = navigated || afterUrl.includes("#") ? "OK" : "FAIL"
      reason = status === "FAIL" ? "hash did not change" : undefined
    } else {
      status = "FAIL"
      reason = "URL did not change after click"
    }
  } else if (expectedPath && !afterPath.startsWith(expectedPath.split("#")[0].split("?")[0])) {
    // Soft check — SPA may redirect (e.g. / -> /home)
    status = "WARN"
    reason = `navigated to unexpected path ${afterPath} (expected ~${expectedPath})`
  }

  if (hitTarget && !hitTarget.isSelfOrChild && status === "FAIL") {
    reason = `${reason || "no navigation"}; click intercepted by <${hitTarget.topTag} class="${hitTarget.topClass}">`
  }

  return {
    label: item.text || "(no text)",
    tag: item.tag,
    href: item.href,
    testId: item.testId,
    beforeUrl: beforePath,
    afterUrl: afterPath,
    navigated,
    status,
    reason,
    clickError,
    hitTarget,
    consoleErrors: consoleErrors.slice(0, 8),
    failedRequests: failedRequests
      .filter((f) => !f.includes("_vercel/insights") && !f.includes("favicon"))
      .slice(0, 8),
  }
}

async function auditMarketing(page, origin) {
  const seed = origin.replace(/\/+$/, "") + "/"
  await page.goto(seed, { waitUntil: "domcontentloaded", timeout: 60_000 })
  await page.waitForTimeout(1000)

  // Open company dropdown so child links are visible
  const companyBtn = page.locator('header button:has-text("Company")').first()
  if (await companyBtn.isVisible().catch(() => false)) {
    await companyBtn.click().catch(() => undefined)
    await page.waitForTimeout(300)
  }

  const candidates = await collectCandidates(page, MARKETING_SELECTORS)
  console.log(`Marketing candidates: ${candidates.length}`)

  const results = []
  for (const item of candidates) {
    // Re-seed each click for isolation
    await page.goto(seed, { waitUntil: "domcontentloaded", timeout: 60_000 }).catch(() => undefined)
    await page.waitForTimeout(400)
    if (item.href?.includes("/about") || item.href?.includes("/blog") || item.href?.includes("/careers") || item.href?.includes("/contact")) {
      const btn = page.locator('header button:has-text("Company")').first()
      if (await btn.isVisible().catch(() => false)) await btn.click().catch(() => undefined)
      await page.waitForTimeout(200)
    }
    // Refresh index after re-render
    const refreshed = await collectCandidates(page, MARKETING_SELECTORS)
    const match =
      refreshed.find((c) => c.href === item.href && c.text === item.text) ||
      refreshed.find((c) => c.href === item.href)
    if (!match) {
      results.push({
        label: item.text,
        tag: item.tag,
        href: item.href,
        status: "SKIPPED",
        reason: "element not found after re-seed",
        beforeUrl: normalizePath(seed),
        afterUrl: normalizePath(page.url()),
        navigated: false,
        consoleErrors: [],
        failedRequests: [],
      })
      continue
    }
    const result = await clickAndObserve(page, match)
    results.push(result)
    console.log(`[${result.status}] ${result.label} -> ${result.afterUrl}${result.reason ? ` (${result.reason})` : ""}`)
  }
  return results
}

async function login(page, origin, email, password) {
  const loginUrl = origin.replace(/\/+$/, "") + "/login?intent=login"
  await page.goto(loginUrl, { waitUntil: "domcontentloaded", timeout: 60_000 })
  await page.getByPlaceholder("you@company.com").fill(email)
  await page.getByPlaceholder("Enter your password").fill(password)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 90_000 })
  // Dismiss common blockers
  await page.waitForTimeout(1500)
  const notNow = page.getByRole("button", { name: "Not now" })
  if (await notNow.isVisible().catch(() => false)) await notNow.click().catch(() => undefined)
  await page.evaluate(() => {
    localStorage.setItem("gravitre-welcome-dismissed", "true")
    localStorage.removeItem("gravitre-nav-expanded")
  })
}

async function waitForSidebar(page, timeout = 120_000) {
  await page.locator("aside nav").waitFor({ state: "visible", timeout })
}

async function auditAppSequential(page, origin) {
  const home = origin.replace(/\/+$/, "") + "/home"
  await page.goto(home, { waitUntil: "domcontentloaded", timeout: 90_000 })
  await waitForSidebar(page)
  await page.waitForTimeout(1000)

  const candidates = await collectCandidates(page, APP_SIDEBAR_SELECTOR)
  console.log(`App sidebar candidates: ${candidates.length}`)

  const results = []
  // Sequential without reset — matches "works for a few then fails"
  for (let n = 0; n < candidates.length; n++) {
    await waitForSidebar(page)
    const refreshed = await collectCandidates(page, APP_SIDEBAR_SELECTOR)
    // Prefer matching by href from original list order
    const targetHref = candidates[n].href
    const match =
      refreshed.find((c) => c.href === targetHref && c.text === candidates[n].text) ||
      refreshed.find((c) => c.href === targetHref) ||
      refreshed[n]

    if (!match) {
      results.push({
        label: candidates[n].text,
        href: targetHref,
        status: "SKIPPED",
        reason: "sidebar link missing mid-crawl",
        beforeUrl: normalizePath(page.url()),
        afterUrl: normalizePath(page.url()),
        navigated: false,
        consoleErrors: [],
        failedRequests: [],
      })
      console.log(`[SKIPPED] ${candidates[n].text}`)
      continue
    }

    const beforeProbe = await page.evaluate(() => ({
      bodyPe: getComputedStyle(document.body).pointerEvents,
      scrollLocked: document.body.hasAttribute("data-scroll-locked"),
      overlays: [...document.querySelectorAll(".fixed.inset-0, [data-slot='dialog-overlay']")].map((el) => ({
        className: String(el.className || "").slice(0, 120),
        z: getComputedStyle(el).zIndex,
        pe: getComputedStyle(el).pointerEvents,
        display: getComputedStyle(el).display,
      })),
    }))

    const result = await clickAndObserve(page, match, { waitMs: 1800 })
    result.overlayProbe = beforeProbe
    results.push(result)
    console.log(
      `[${result.status}] ${result.label} ${result.beforeUrl} -> ${result.afterUrl}` +
        (result.reason ? ` (${result.reason})` : "") +
        (beforeProbe.overlays.length ? ` overlays=${beforeProbe.overlays.length}` : ""),
    )

    // If failed, capture screenshot + DOM snapshot snippet
    if (result.status === "FAIL") {
      const shot = path.join("/tmp", `click-audit-fail-${n}.png`)
      await page.screenshot({ path: shot, fullPage: false }).catch(() => undefined)
      result.screenshot = shot
    }
  }
  return results
}

async function auditAppIsolated(page, origin) {
  const home = origin.replace(/\/+$/, "") + "/home"
  await page.goto(home, { waitUntil: "domcontentloaded", timeout: 90_000 })
  await waitForSidebar(page)
  const candidates = await collectCandidates(page, APP_SIDEBAR_SELECTOR)
  console.log(`App isolated candidates: ${candidates.length}`)

  const results = []
  for (const item of candidates) {
    await page.goto(home, { waitUntil: "domcontentloaded", timeout: 90_000 }).catch(() => undefined)
    await waitForSidebar(page)
    await page.waitForTimeout(500)
    const refreshed = await collectCandidates(page, APP_SIDEBAR_SELECTOR)
    const match = refreshed.find((c) => c.href === item.href && c.text === item.text) || refreshed.find((c) => c.href === item.href)
    if (!match) {
      results.push({ label: item.text, href: item.href, status: "SKIPPED", reason: "missing after reset", navigated: false, beforeUrl: "/home", afterUrl: normalizePath(page.url()), consoleErrors: [], failedRequests: [] })
      continue
    }
    const result = await clickAndObserve(page, match, { waitMs: 1800 })
    results.push(result)
    console.log(`[${result.status}] ${result.label} -> ${result.afterUrl}${result.reason ? ` (${result.reason})` : ""}`)
  }
  return results
}

function printReport(title, results) {
  console.log(`\n\n================ ${title} ================\n`)
  let fail = 0
  let warn = 0
  let ok = 0
  for (const r of results) {
    if (r.status === "FAIL" || r.status === "SKIPPED") fail++
    else if (r.status === "WARN") warn++
    else ok++
    console.log(`[${r.status.padEnd(7)}] <${r.tag || "a"}> "${r.label}"`)
    if (r.href) console.log(`         href: ${r.href}`)
    console.log(`         before: ${r.beforeUrl}`)
    console.log(`         after:  ${r.afterUrl}`)
    if (r.reason) console.log(`         reason: ${r.reason}`)
    if (r.hitTarget && !r.hitTarget.isSelfOrChild) {
      console.log(`         hitTarget: <${r.hitTarget.topTag}> ${r.hitTarget.topClass}`)
      console.log(`         bodyPE=${r.hitTarget.bodyPointerEvents} scrollLocked=${r.hitTarget.scrollLocked}`)
    }
    if (r.overlayProbe?.overlays?.length) {
      console.log(`         overlays before click:`)
      r.overlayProbe.overlays.forEach((o) => console.log(`           - z=${o.z} pe=${o.pe} ${o.className}`))
    }
    if (r.consoleErrors?.length) {
      console.log(`         console:`)
      r.consoleErrors.forEach((e) => console.log(`           - ${e}`))
    }
    if (r.failedRequests?.length) {
      console.log(`         failed reqs:`)
      r.failedRequests.forEach((e) => console.log(`           - ${e}`))
    }
    if (r.screenshot) console.log(`         screenshot: ${r.screenshot}`)
    console.log("")
  }
  console.log(`Summary: OK=${ok} WARN=${warn} FAIL/SKIP=${fail} TOTAL=${results.length}\n`)
  return { ok, warn, fail, total: results.length }
}

;(async () => {
  const origin = START_URL.replace(/\/+$/, "").replace(/\/login.*/, "")
  console.log(`Mode=${mode} origin=${origin} headless=${HEADLESS}`)

  const browser = await chromium.launch({ headless: HEADLESS })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    userAgent:
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  })
  const page = await context.newPage()

  const report = { marketing: null, appSequential: null, appIsolated: null }

  try {
    if (mode === "marketing" || mode === "both") {
      const marketing = await auditMarketing(page, origin)
      report.marketing = printReport("MARKETING", marketing)
    }

    if (mode === "app" || mode === "both" || mode === "app-sequential" || mode === "app-isolated") {
      if (!EMAIL || !PASSWORD) {
        console.error("\nApp audit requires --email and --password (or CLICK_AUDIT_EMAIL / CLICK_AUDIT_PASSWORD).")
        console.error("Skipping authenticated web-app crawl.\n")
      } else {
        await login(page, origin, EMAIL, PASSWORD)
        console.log(`Logged in as ${EMAIL}; current=${page.url()}`)

        if (mode === "app" || mode === "both" || mode === "app-sequential") {
          const seq = await auditAppSequential(page, origin)
          report.appSequential = printReport("APP SIDEBAR (sequential, no reset)", seq)
        }
        if (mode === "app" || mode === "both" || mode === "app-isolated") {
          const iso = await auditAppIsolated(page, origin)
          report.appIsolated = printReport("APP SIDEBAR (isolated reset to /home)", iso)
        }
      }
    }
  } finally {
    const outDir = process.env.CLICK_AUDIT_OUT_DIR || path.join(__dirname, "..", "docs", "delivery")
    fs.mkdirSync(outDir, { recursive: true })
    const out = path.join(outDir, "phase4-click-audit-live.json")
    fs.writeFileSync(out, JSON.stringify(report, null, 2))
    console.log(`Wrote ${out}`)
    await browser.close()
  }
})().catch((err) => {
  console.error(err)
  process.exit(1)
})
