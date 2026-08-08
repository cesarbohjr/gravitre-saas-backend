/**
 * Captures the four assurance states (light + dark) from the design-review comp
 * at /e2e/shots/outcome-states.
 *
 * Playwright rather than agent-browser: agent-browser runs in a separate browser
 * sandbox where localhost is not reliably bridged, while Playwright runs in the
 * project sandbox and can always reach the dev server.
 *
 * Usage: node scripts/capture-outcome-states.mjs
 */

import { chromium } from "@playwright/test"
import { mkdirSync } from "node:fs"

const BASE = process.env.SHOT_BASE_URL || "http://localhost:3000"
const URL = `${BASE}/e2e/shots/outcome-states`
const OUT = "/tmp/agent-browser"

// The dev overlay bakes a red "N Issues" badge into the corner of every shot.
// Hide the portal host via CSS: clicking the toast EXPANDS the full-screen error
// panel instead of dismissing it, which silently replaces the whole screenshot.
const HIDE_DEV_OVERLAY = `
  nextjs-portal,
  [data-nextjs-toast],
  [data-nextjs-dev-tools-button] { display: none !important; }
`

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()

for (const theme of ["light", "dark"]) {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 1100 },
    deviceScaleFactor: 2,
    colorScheme: theme,
  })

  // next-themes reads its choice from localStorage and reapplies the html class
  // on hydration, so setting the class directly gets reverted. Seed the store
  // before any script runs instead.
  await page.addInitScript((t) => localStorage.setItem("theme", t), theme)

  await page.goto(URL, { waitUntil: "networkidle" })
  await page.getByText("Flagged for review").first().waitFor({ timeout: 20000 })

  const applied = await page.evaluate(() => ({
    htmlClass: document.documentElement.className,
    // Proves the mesh + scrim actually resolved rather than falling back.
    canvasBg: getComputedStyle(document.querySelector(".ai-chat-canvas")).backgroundColor,
    // The card the comp exists to interrogate.
    flaggedBg: getComputedStyle(document.querySelector('[data-outcome-state="flagged"]')).backgroundColor,
    verifiedBg: getComputedStyle(document.querySelector('[data-outcome-state="verified"]')).backgroundColor,
    states: [...document.querySelectorAll("[data-outcome-state]")].map((el) =>
      el.getAttribute("data-outcome-state"),
    ),
  }))
  console.log(theme, JSON.stringify(applied))

  await page.addStyleTag({ content: HIDE_DEV_OVERLAY }).catch(() => {})
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/outcome-states-${theme}.png`, fullPage: true })
  await page.close()
}

await browser.close()
console.log("done")
