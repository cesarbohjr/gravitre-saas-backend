/**
 * Prompt 3 Phase 2 — authenticated deep-surface click + empty-state audit.
 *
 * Covers major app surfaces beyond sidebar-only crawl:
 *   /ai, /activity, /agents, /settings (personal/org/admin), /connectors,
 *   /extension/connect
 *
 * For each surface: page load health, empty-state quality, sample interactive
 * controls (dead-click / no network / mock signals).
 *
 * Usage:
 *   node scripts/prompt3-authenticated-click-audit.js https://gravitre.app \
 *     --email conversation-smoke-sa@gravitre.app --password '...'
 *
 * Env: CLICK_AUDIT_EMAIL / CLICK_AUDIT_PASSWORD
 * Out: docs/delivery/prompt3-phase2-click-audit-live.json
 */

const { chromium } = require("playwright")
const fs = require("node:fs")
const path = require("node:path")

const START_URL = process.argv[2] || "https://gravitre.app"

function argValue(flag) {
  const idx = process.argv.indexOf(flag)
  return idx >= 0 ? process.argv[idx + 1] : undefined
}

const EMAIL = argValue("--email") || process.env.CLICK_AUDIT_EMAIL || ""
const PASSWORD = argValue("--password") || process.env.CLICK_AUDIT_PASSWORD || ""
const HEADLESS = process.env.CLICK_AUDIT_HEADED !== "1"
const OUT =
  process.env.CLICK_AUDIT_OUT ||
  path.join(__dirname, "..", "docs", "delivery", "prompt3-phase2-click-audit-live.json")

const SURFACES = [
  { id: "chat_ai", path: "/ai", mustHave: [/ai|chat|assistant|message|composer|prompt/i] },
  { id: "activity_outcomes", path: "/activity", mustHave: [/activity|outcome|run|history|empty/i] },
  { id: "agents_hub", path: "/agents", mustHave: [/agent|swarm|create|empty/i] },
  { id: "settings_personal_profile", path: "/settings/profile", tier: "personal", mustHave: [/profile|name|email|account/i] },
  { id: "settings_personal_orgs", path: "/settings/organizations", tier: "personal", mustHave: [/organization|workspace|member/i] },
  { id: "settings_org", path: "/settings?section=organization", tier: "organization", mustHave: [/organization|brand|workspace/i] },
  { id: "settings_ai_models", path: "/settings?section=ai-models", tier: "organization", mustHave: [/model|ai|memory/i] },
  { id: "settings_admin_audit", path: "/settings?section=audit", tier: "admin", mustHave: [/audit|event|log|admin|permission|empty/i] },
  { id: "settings_admin_enterprise", path: "/settings/enterprise", tier: "admin", mustHave: [/enterprise|sso|federation|admin|empty/i] },
  { id: "connectors", path: "/connectors", mustHave: [/connector|integrat|connect|hubspot|apollo|empty/i] },
  { id: "extension_connect", path: "/extension/connect", mustHave: [/extension|connect|chrome|install|browser/i] },
]

const INTERACTIVE_SELECTOR = [
  "main button:not([disabled])",
  "main a[href]",
  "main [role='button']:not([aria-disabled='true'])",
  "[data-testid] button:not([disabled])",
].join(", ")

function normalizePath(url) {
  try {
    const u = new URL(url)
    return (u.pathname.replace(/\/+$/, "") || "/") + u.search
  } catch {
    return url
  }
}

async function login(page, origin, email, password) {
  const loginUrl = origin.replace(/\/+$/, "") + "/login?intent=login"
  const home = origin.replace(/\/+$/, "") + "/home"
  await page.goto(loginUrl, { waitUntil: "domcontentloaded", timeout: 60_000 })
  await page.getByPlaceholder("you@company.com").fill(email)
  await page.getByPlaceholder("Enter your password").fill(password)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 90_000 })
  await page.waitForTimeout(1200)
  const notNow = page.getByRole("button", { name: "Not now" })
  if (await notNow.isVisible().catch(() => false)) await notNow.click().catch(() => undefined)
  await page.evaluate(() => {
    localStorage.setItem("gravitre-welcome-dismissed", "true")
    localStorage.removeItem("gravitre-nav-expanded")
    // Prefer operator shell for deep-surface audit (smoke SA may land in Lite).
    localStorage.setItem("gravitre-view-mode", "admin")
    localStorage.setItem(
      "gravitre:selectedOrg",
      JSON.stringify({
        id: "f07e57c0-1501-4000-8000-c04e57a00001",
        name: "Gravitre Isolated Conversation Smoke",
      }),
    )
  })
  // Reload so view-mode + org take effect before crawling.
  await page.goto(home, { waitUntil: "domcontentloaded", timeout: 90_000 })
  await page.waitForTimeout(1000)
  await dismissBlockers(page)
  // Auth must stick — bounce back to /login is a hard failure (not a soft surface WARN).
  if (page.url().includes("/login")) {
    throw new Error(`login did not stick; landed on ${page.url()}`)
  }
  await page.locator("aside nav").waitFor({ state: "visible", timeout: 90_000 })
}

async function dismissBlockers(page) {
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press("Escape").catch(() => undefined)
    await page.waitForTimeout(120)
  }
  for (const name of ["Not now", "Dismiss", "Got it", "Close", "Skip", "Cancel"]) {
    const btn = page.getByRole("button", { name, exact: false }).first()
    if (await btn.isVisible().catch(() => false)) await btn.click({ force: true }).catch(() => undefined)
  }
  // Radix dialog overlay can stick after command-palette navigation.
  const overlay = page.locator('[data-slot="dialog-overlay"][data-state="open"]')
  if (await overlay.count().catch(() => 0)) {
    await overlay.first().click({ force: true }).catch(() => undefined)
    await page.keyboard.press("Escape").catch(() => undefined)
  }
  await page.waitForTimeout(200)
}

async function emptyStateProbe(page) {
  return page.evaluate(() => {
    const main = document.querySelector("main") || document.body
    const text = (main.innerText || "").replace(/\s+/g, " ").trim()
    const spinners = [
      ...document.querySelectorAll(
        "[data-loading='true'], [aria-busy='true'], .animate-spin, [class*='spinner'], [class*='Skeleton']",
      ),
    ].filter((el) => {
      const style = getComputedStyle(el)
      return style.display !== "none" && style.visibility !== "hidden"
    })
    const emptyMarkers = [...document.querySelectorAll("[data-empty], [data-testid*='empty']")].map((el) =>
      (el.innerText || el.getAttribute("aria-label") || "").trim().slice(0, 160),
    )
    const helpful =
      text.length >= 40 ||
      emptyMarkers.some((t) => t.length >= 12) ||
      /get started|no .* yet|connect|create|empty|nothing here|try/i.test(text)
    return {
      textLen: text.length,
      textPreview: text.slice(0, 220),
      visibleSpinners: spinners.length,
      emptyMarkers: emptyMarkers.slice(0, 6),
      helpful,
      blank: text.length < 12 && spinners.length === 0,
    }
  })
}

async function sampleInteractives(page, { max = 8 } = {}) {
  const locs = page.locator(INTERACTIVE_SELECTOR)
  const count = await locs.count()
  const findings = []
  const limit = Math.min(count, max)
  for (let i = 0; i < limit; i++) {
    const loc = locs.nth(i)
    if (!(await loc.isVisible().catch(() => false))) continue
    const meta = await loc.evaluate((el) => ({
      tag: el.tagName.toLowerCase(),
      text: (el.innerText || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ").slice(0, 80),
      href: el.getAttribute("href") || "",
      type: el.getAttribute("type") || "",
      disabled: el.hasAttribute("disabled") || el.getAttribute("aria-disabled") === "true",
      testId: el.getAttribute("data-testid") || "",
    }))
    if (!meta.text && !meta.href) continue
    // Skip shell chrome / destructive / billing — not surface under test
    if (
      /delete|remove|sign out|log out|cancel plan|purchase|buy|toggle navigation|^lite$|^admin$|search or command|search conversations|toggle theme|investigating failed|upgrade now|notifications|view all notifications|gravitre isolated/i.test(
        meta.text,
      )
    ) {
      findings.push({ ...meta, status: "SKIPPED", reason: "shell_chrome_or_destructive" })
      continue
    }
    await dismissBlockers(page)

    const beforeUrl = page.url()
    const apiHits = []
    const onReq = (req) => {
      const u = req.url()
      if (/api\.gravitre\.app|\/api\//.test(u) && !/_next|favicon|analytics/.test(u)) {
        apiHits.push(`${req.method()} ${u.slice(0, 160)}`)
      }
    }
    page.on("request", onReq)
    let clickError = null
    try {
      await loc.click({ timeout: 5_000 })
      await page.waitForTimeout(900)
    } catch (err) {
      clickError = err instanceof Error ? err.message : String(err)
    } finally {
      page.off("request", onReq)
    }
    const afterUrl = page.url()
    const navigated = normalizePath(afterUrl) !== normalizePath(beforeUrl)
    let status = "OK"
    let reason
    if (clickError) {
      status = "FAIL"
      reason = `click error: ${clickError}`
    } else if (meta.href && !navigated && !meta.href.startsWith("#")) {
      // Link that didn't navigate — may be SPA same-route or dead
      if (meta.href.includes("javascript:") || meta.href === "#") {
        status = "FAIL"
        reason = "dead_href"
      } else {
        status = apiHits.length ? "OK" : "WARN"
        reason = apiHits.length ? "same_route_with_api" : "no_nav_no_api"
      }
    } else if (!meta.href && !navigated && apiHits.length === 0) {
      // Button with no observable effect
      status = "WARN"
      reason = "no_observable_effect"
    }

    findings.push({
      ...meta,
      status,
      reason,
      navigated,
      apiHits: apiHits.slice(0, 4),
      beforeUrl: normalizePath(beforeUrl),
      afterUrl: normalizePath(afterUrl),
    })

    // Restore surface if we navigated away
    if (navigated) {
      await page.goBack({ waitUntil: "domcontentloaded" }).catch(() => undefined)
      await page.waitForTimeout(400)
      await dismissBlockers(page)
    } else {
      await dismissBlockers(page)
    }
  }
  return findings
}

async function auditSurface(page, origin, surface) {
  const url = origin.replace(/\/+$/, "") + surface.path
  const started = Date.now()
  const consoleErrors = []
  const failedApi = []
  const onConsole = (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 240))
  }
  const onFailed = (req) => {
    const u = req.url()
    if (/api\.gravitre\.app|\/api\//.test(u)) {
      failedApi.push(`${req.method()} ${u.slice(0, 160)} — ${req.failure()?.errorText || "failed"}`)
    }
  }
  page.on("console", onConsole)
  page.on("requestfailed", onFailed)

  let loadError = null
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90_000 })
    await page.waitForTimeout(1800)
    await dismissBlockers(page)
    // Wait out initial skeletons; settings auth/admin boot can take several seconds.
    await page.waitForTimeout(2500)
    await dismissBlockers(page)
    // If still spinner-only, wait once more (settings boot timeout is 12s client-side).
    const probeEarly = await emptyStateProbe(page)
    if (probeEarly.visibleSpinners > 0 && probeEarly.textLen < 40) {
      await page.waitForTimeout(10_000)
      await dismissBlockers(page)
    }
  } catch (err) {
    loadError = err instanceof Error ? err.message : String(err)
  }

  const empty = loadError ? null : await emptyStateProbe(page)
  const bodyText = empty?.textPreview || ""
  const contentMatch = surface.mustHave.some((re) => re.test(bodyText) || re.test(page.url()))
  const infiniteSpinner = empty && empty.visibleSpinners > 0 && empty.textLen < 40
  const blankEmpty = empty && (empty.blank || (!empty.helpful && empty.textLen < 40))

  let interactives = []
  if (!loadError) {
    interactives = await sampleInteractives(page, { max: 6 })
  }

  page.off("console", onConsole)
  page.off("requestfailed", onFailed)

  const dead = interactives.filter((f) => f.status === "FAIL")
  const warns = interactives.filter((f) => f.status === "WARN")

  let status = "OK"
  const issues = []
  if (loadError) {
    status = "FAIL"
    issues.push(`load_error: ${loadError}`)
  }
  if (infiniteSpinner) {
    status = "FAIL"
    issues.push("infinite_or_stuck_spinner_with_thin_content")
  }
  if (blankEmpty) {
    status = status === "FAIL" ? "FAIL" : "WARN"
    issues.push("blank_or_unhelpful_empty_state")
  }
  if (!contentMatch && !loadError) {
    status = status === "FAIL" ? "FAIL" : "WARN"
    issues.push("surface_content_cues_missing")
  }
  if (dead.length) {
    status = "FAIL"
    issues.push(`dead_controls=${dead.length}`)
  }

  return {
    id: surface.id,
    path: surface.path,
    tier: surface.tier || null,
    finalUrl: normalizePath(page.url()),
    loadMs: Date.now() - started,
    status,
    issues,
    empty,
    contentMatch,
    interactives,
    deadControls: dead,
    warnControls: warns,
    consoleErrors: consoleErrors.slice(0, 8),
    failedApi: failedApi.slice(0, 8),
  }
}

async function auditSidebarIsolated(page, origin) {
  // Reuse pattern from click-audit.js (authoritative nav check)
  const home = origin.replace(/\/+$/, "") + "/home"
  await page.goto(home, { waitUntil: "domcontentloaded", timeout: 90_000 })
  await page.locator("aside nav").waitFor({ state: "visible", timeout: 120_000 })
  const hrefs = await page.locator("aside nav a[href]").evaluateAll((els) =>
    els
      .filter((el) => el.offsetParent !== null)
      .map((el) => ({
        href: el.getAttribute("href"),
        text: (el.innerText || "").trim().replace(/\s+/g, " ").slice(0, 60),
      })),
  )
  const results = []
  for (const item of hrefs) {
    await page.goto(home, { waitUntil: "domcontentloaded", timeout: 90_000 }).catch(() => undefined)
    await page.locator("aside nav").waitFor({ state: "visible", timeout: 60_000 })
    await page.waitForTimeout(400)
    await dismissBlockers(page)
    const link = page.locator(`aside nav a[href='${item.href}']`).first()
    const before = normalizePath(page.url())
    const targetPath = item.href
      ? normalizePath(new URL(item.href, origin).href).split("?")[0]
      : null
    // Already on destination (e.g. /home while seeded on /home) is OK.
    if (targetPath && before.split("?")[0] === targetPath) {
      results.push({
        label: item.text,
        href: item.href,
        before,
        after: before,
        status: "OK",
        reason: "already on target",
      })
      continue
    }
    // Onboarding /welcome can appear in href list but be collapsed/hidden.
    if (!(await link.isVisible().catch(() => false))) {
      results.push({
        label: item.text,
        href: item.href,
        before,
        after: before,
        status: "SKIPPED",
        reason: "sidebar link not visible",
      })
      continue
    }
    let status = "OK"
    let reason
    try {
      await link.click({ timeout: 8_000 })
      await page.waitForTimeout(1200)
    } catch (err) {
      status = "FAIL"
      reason = err instanceof Error ? err.message : String(err)
    }
    const after = normalizePath(page.url())
    if (status === "OK" && after === before && item.href && !item.href.startsWith("#")) {
      status = "FAIL"
      reason = "URL did not change after click"
    }
    results.push({ label: item.text, href: item.href, before, after, status, reason })
  }
  return results
}

;(async () => {
  if (!EMAIL || !PASSWORD) {
    console.error("Requires --email/--password or CLICK_AUDIT_EMAIL/PASSWORD")
    process.exit(2)
  }
  const origin = START_URL.replace(/\/+$/, "").replace(/\/login.*/, "")
  console.log(`Prompt3 click-audit origin=${origin} user=${EMAIL} headless=${HEADLESS}`)

  const browser = await chromium.launch({ headless: HEADLESS })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  })
  const page = await context.newPage()
  const report = {
    feature: "prompt3_phase2_authenticated_click_audit",
    checked_at: new Date().toISOString(),
    origin,
    email: EMAIL,
    surfaces: [],
    sidebar: [],
  }

  try {
    await login(page, origin, EMAIL, PASSWORD)
    console.log(`Logged in -> ${page.url()}`)

    for (const surface of SURFACES) {
      const result = await auditSurface(page, origin, surface)
      report.surfaces.push(result)
      console.log(`[${result.status}] ${result.id} ${result.path} issues=${result.issues.join(",") || "none"}`)
    }

    try {
      report.sidebar = await auditSidebarIsolated(page, origin)
      const sideFail = report.sidebar.filter((r) => r.status === "FAIL").length
      console.log(`Sidebar isolated: fail=${sideFail}/${report.sidebar.length}`)
    } catch (err) {
      report.sidebar_error = err instanceof Error ? err.message : String(err)
      console.error(`Sidebar audit aborted: ${report.sidebar_error}`)
    }
  } finally {
    const surfaceFail = report.surfaces.filter((s) => s.status === "FAIL").length
    const surfaceWarn = report.surfaces.filter((s) => s.status === "WARN").length
    const sideFail = report.sidebar.filter((r) => r.status === "FAIL").length
    const deadButtons = report.surfaces.flatMap((s) => s.deadControls || [])
    const emptyGaps = report.surfaces.filter((s) =>
      (s.issues || []).some((i) => i.includes("empty") || i.includes("spinner") || i.includes("blank")),
    )
    report.summary = {
      surfaces_ok: report.surfaces.filter((s) => s.status === "OK").length,
      surfaces_warn: surfaceWarn,
      surfaces_fail: surfaceFail,
      surfaces_total: report.surfaces.length,
      sidebar_fail: sideFail,
      sidebar_total: report.sidebar.length,
      dead_controls: deadButtons.length,
      empty_state_gaps: emptyGaps.map((s) => s.id),
    }
    // Authoritative: surface FAIL or sidebar FAIL → overall FAIL; WARN-only → PARTIAL
    report.verdict =
      surfaceFail > 0 || sideFail > 0 ? "FAIL" : surfaceWarn > 0 ? "PARTIAL" : "PASS"
    fs.mkdirSync(path.dirname(OUT), { recursive: true })
    fs.writeFileSync(OUT, JSON.stringify(report, null, 2))
    console.log(`Wrote ${OUT} verdict=${report.verdict}`)
    await browser.close()
  }
  process.exit(report.verdict === "FAIL" ? 1 : 0)
})().catch((err) => {
  console.error(err)
  process.exit(1)
})
