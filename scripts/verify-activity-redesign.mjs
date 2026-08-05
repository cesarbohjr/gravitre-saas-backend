/**
 * Verifies the /activity redesign against the shots harness.
 *
 * The acceptance criterion for "too much long scroll" is structural, not
 * visual: at lg+ the document must not scroll, and the list + detail panes must
 * each scroll internally instead. Screenshots alone can't prove that, so this
 * asserts scrollHeight directly and captures PNGs for the visual review.
 *
 * Run against a local `next dev` (apps/web). /e2e/shots is allowed in
 * non-production without PLAYWRIGHT_E2E; AppShell also bypasses billing
 * bootstrap on /e2e/* so list fixtures can hydrate. Do not use this script to
 * debug product /activity while logged out — that path needs a real session.
 */

import { chromium } from "@playwright/test"
import { mkdir } from "node:fs/promises"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000"
const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const OUT = process.env.OUT_DIR ?? join(REPO_ROOT, "docs", "delivery", "_artifacts", "activity-redesign")

const DESKTOP = { width: 1440, height: 900 }
const PREVIEW = { width: 845, height: 841 }

const failures = []
function check(label, condition, detail) {
  const ok = Boolean(condition)
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`)
  if (!ok) failures.push(label)
}

async function paneMetrics(page) {
  return page.evaluate(() => {
    const scrollers = Array.from(document.querySelectorAll("div, section")).filter((el) => {
      const style = getComputedStyle(el)
      return (
        (style.overflowY === "auto" || style.overflowY === "scroll") &&
        el.scrollHeight > el.clientHeight + 2
      )
    })
    return {
      docScrollHeight: document.documentElement.scrollHeight,
      innerHeight: window.innerHeight,
      internalScrollers: scrollers.length,
      scrollerHeights: scrollers.map((el) => `${el.clientHeight}/${el.scrollHeight}`),
    }
  })
}

const browser = await chromium.launch()

try {
  await mkdir(OUT, { recursive: true })
  const context = await browser.newContext({ viewport: DESKTOP, colorScheme: "dark" })
  const page = await context.newPage()

  page.on("console", (msg) => {
    if (msg.type() === "error") console.log(`  [console.error] ${msg.text()}`)
  })
  page.on("pageerror", (err) => console.log(`  [pageerror] ${err.message}`))

  // ---- All tab, desktop -----------------------------------------------------
  await page.goto(`${BASE}/e2e/shots/activity`, { waitUntil: "networkidle" })
  await page.waitForSelector('[role="listbox"]', { timeout: 20_000 })
  await page.waitForTimeout(700)

  const rows = await page.locator('[role="option"]').count()
  check("list renders rows", rows > 0, `${rows} rows`)

  const desktop = await paneMetrics(page)
  check(
    "document does not scroll at lg",
    desktop.docScrollHeight <= desktop.innerHeight + 2,
    `doc ${desktop.docScrollHeight} vs viewport ${desktop.innerHeight}`,
  )
  check(
    "panes scroll internally",
    desktop.internalScrollers >= 1,
    `${desktop.internalScrollers} scroller(s): ${desktop.scrollerHeights.join(", ")}`,
  )

  const selectedCount = await page.locator('[role="option"][aria-selected="true"]').count()
  check("exactly one row selected by default", selectedCount === 1, `${selectedCount} selected`)

  await page.screenshot({ path: `${OUT}/activity-all-desktop.png`, fullPage: false })

  // ---- Keyboard navigation --------------------------------------------------
  const firstTitle = await page
    .locator('[role="option"][aria-selected="true"]')
    .first()
    .innerText()
  await page.locator('[role="option"]').first().focus()
  await page.keyboard.press("ArrowDown")
  await page.waitForTimeout(400)
  const afterTitle = await page
    .locator('[role="option"][aria-selected="true"]')
    .first()
    .innerText()
  check("ArrowDown moves selection", firstTitle !== afterTitle, "selection changed")

  const detailText = await page.locator("[data-business-outcome-id]").first().innerText()
  check(
    "detail pane tracks selection",
    detailText.length > 0,
    `${detailText.slice(0, 40).replace(/\n/g, " ")}…`,
  )
  await page.screenshot({ path: `${OUT}/activity-keyboard-selected.png` })

  // ---- Collapsible detail sections ----------------------------------------
  const triggers = page.locator('[data-business-outcome-id] [data-slot="collapsible-trigger"]')
  const triggerCount = await triggers.count()
  check("detail sections are collapsible", triggerCount > 0, `${triggerCount} triggers`)

  if (triggerCount > 0) {
    const closed = await page
      .locator('[data-business-outcome-id] [data-slot="collapsible-trigger"][data-state="closed"]')
      .count()
    check("some sections start collapsed", closed > 0, `${closed} collapsed`)

    const target = page
      .locator('[data-business-outcome-id] [data-slot="collapsible-trigger"][data-state="closed"]')
      .first()
    const label = await target.innerText()
    await target.click()
    await page.waitForTimeout(400)
    check(
      "collapsed section expands on click",
      (await target.getAttribute("data-state")) === "open",
      label.replace(/\n/g, " ").trim(),
    )
    await page.screenshot({ path: `${OUT}/activity-section-expanded.png` })
  }

  // ---- Failures tab --------------------------------------------------------
  await page.goto(`${BASE}/e2e/shots/activity?tab=failures`, { waitUntil: "networkidle" })
  await page.waitForTimeout(1200)
  const failuresBody = await page.locator("body").innerText()
  const sawAlert = failuresBody.includes("HubSpot token expires")
  check("failure fixture renders", sawAlert, sawAlert ? "critical alert present" : "not found")

  const groupTriggers = await page.locator('[data-slot="collapsible-trigger"]').count()
  check("severity groups are collapsible", groupTriggers > 0, `${groupTriggers} triggers`)

  const failuresMetrics = await paneMetrics(page)
  check(
    "failures tab does not scroll the document",
    failuresMetrics.docScrollHeight <= failuresMetrics.innerHeight + 2,
    `doc ${failuresMetrics.docScrollHeight} vs viewport ${failuresMetrics.innerHeight}`,
  )
  await page.screenshot({ path: `${OUT}/activity-failures-desktop.png` })

  // ---- Preview viewport (stacked, page scroll is expected here) ------------
  await page.setViewportSize(PREVIEW)
  await page.goto(`${BASE}/e2e/shots/activity`, { waitUntil: "networkidle" })
  await page.waitForTimeout(900)
  await page.screenshot({ path: `${OUT}/activity-preview-845.png`, fullPage: false })

  // ---- Shared-component regression checks ---------------------------------
  await page.setViewportSize(DESKTOP)
  for (const route of ["agents", "ai"]) {
    await page.goto(`${BASE}/e2e/shots/${route}`, { waitUntil: "networkidle" })
    await page.waitForTimeout(1000)
    await page.screenshot({ path: `${OUT}/regression-${route}.png` })
    console.log(`captured regression-${route}.png`)
  }

  console.log(
    failures.length ? `\n${failures.length} CHECK(S) FAILED: ${failures.join(", ")}` : "\nALL CHECKS PASSED",
  )
  process.exitCode = failures.length ? 1 : 0
} finally {
  await browser.close()
}
