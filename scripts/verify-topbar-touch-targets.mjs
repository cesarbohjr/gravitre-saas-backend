/**
 * Measures every interactive element in the app top bar and asserts that, on
 * phone viewports, each one meets the 44x44px minimum touch target. Also
 * asserts the right-hand control cluster does not overflow horizontally.
 *
 * Playwright runs inside the project sandbox, so it can reach the local dev
 * server (the browser-automation sandbox generally cannot).
 *
 * Prereqs — dev server must already be running with the e2e harness enabled:
 *   PLAYWRIGHT_E2E=1 NEXT_PUBLIC_PLAYWRIGHT_E2E=1 pnpm dev
 *   pnpm exec playwright install chromium   # once, if the browser is missing
 *
 * Usage:
 *   node scripts/verify-topbar-touch-targets.mjs
 */
import { chromium } from "@playwright/test"
import { mkdir } from "node:fs/promises"

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"
const ROUTE = "/e2e/shots/activity"
const OUT_DIR = ".playwright-out"
const MIN_TOUCH_PX = 44

const VIEWPORTS = [
  { name: "phone", width: 390, height: 844, enforce: true },
  { name: "phone-small", width: 320, height: 700, enforce: true },
  { name: "desktop", width: 1440, height: 900, enforce: false },
]

/** Elements the user cannot tap on a phone are excluded from enforcement. */
const INTERACTIVE = "button, a[href], [role='button'], input, select"

async function measure(page) {
  return page.$$eval(
    `header ${INTERACTIVE.split(", ").join(", header ")}`,
    (nodes, minPx) =>
      nodes
        .map((el) => {
          const rect = el.getBoundingClientRect()
          const style = getComputedStyle(el)
          const hidden =
            style.display === "none" ||
            style.visibility === "hidden" ||
            rect.width === 0 ||
            rect.height === 0
          const label = (
            el.getAttribute("aria-label") ||
            el.textContent?.trim().replace(/\s+/g, " ").slice(0, 32) ||
            el.tagName.toLowerCase()
          ).trim()
          return {
            label,
            width: Math.round(rect.width * 10) / 10,
            height: Math.round(rect.height * 10) / 10,
            hidden,
            ok: hidden || (rect.width >= minPx && rect.height >= minPx),
          }
        })
        .filter((m) => !m.hidden),
    MIN_TOUCH_PX,
  )
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true })
  const browser = await chromium.launch()
  const failures = []

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
      colorScheme: "dark",
    })
    const page = await context.newPage()
    const res = await page.goto(`${BASE_URL}${ROUTE}`, { waitUntil: "networkidle" })

    if (!res || res.status() !== 200) {
      failures.push(`${vp.name}: ${ROUTE} returned ${res ? res.status() : "no response"}`)
      await context.close()
      continue
    }
    // Assert we're on the harness, not redirected to prod/login by the proxy.
    const host = new URL(page.url()).host
    if (!host.startsWith("localhost")) {
      failures.push(`${vp.name}: redirected off localhost to ${host}`)
      await context.close()
      continue
    }

    const header = page.locator("header").first()
    await header.waitFor({ state: "visible" })

    const measurements = await measure(page)
    console.log(`\n${vp.name} (${vp.width}x${vp.height}) — ${measurements.length} visible controls`)
    for (const m of measurements) {
      const flag = vp.enforce && !m.ok ? "FAIL" : "ok  "
      console.log(`  ${flag} ${m.width}x${m.height}  ${m.label}`)
      if (vp.enforce && !m.ok) {
        failures.push(`${vp.name}: "${m.label}" is ${m.width}x${m.height}, need >=${MIN_TOUCH_PX}`)
      }
    }

    // No horizontal overflow: the header must not scroll sideways.
    const overflow = await page.evaluate(() => {
      const h = document.querySelector("header")
      if (!h) return null
      return { scrollWidth: h.scrollWidth, clientWidth: h.clientWidth }
    })
    if (overflow && overflow.scrollWidth > overflow.clientWidth + 1) {
      failures.push(
        `${vp.name}: header overflows horizontally (${overflow.scrollWidth} > ${overflow.clientWidth})`,
      )
    } else {
      console.log(`  ok   no horizontal overflow (${overflow?.scrollWidth}/${overflow?.clientWidth})`)
    }

    const shot = `${OUT_DIR}/topbar-${vp.name}-${Date.now()}.png`
    await header.screenshot({ path: shot })
    console.log(`  shot ${shot}`)

    await context.close()
  }

  await browser.close()

  if (failures.length) {
    console.error(`\n${failures.length} failure(s):`)
    for (const f of failures) console.error(`  - ${f}`)
    process.exit(1)
  }
  console.log("\nAll top-bar touch targets pass.")
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
