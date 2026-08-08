/**
 * Captures the consolidated Billing & Plan surface in light and dark theme.
 *
 * Assertions here exist because a wrong fixture fails as a plausible-looking
 * empty state rather than an error: voice_minutes_billing_visible gates the
 * whole voice block, and a bad usage.tier collapses the grid to placeholders.
 * A screenshot of that would still "look fine", so the run fails loudly
 * instead of quietly producing useless evidence.
 *
 *   PLAYWRIGHT_BASE_URL=http://localhost:3000 node scripts/capture-billing-states.mjs
 */

import { mkdir } from "node:fs/promises"
import { chromium } from "@playwright/test"

const BASE = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"
const URL = `${BASE}/e2e/shots/billing-states`
const OUT = "docs/delivery/shots/billing-states"

const EXPECTED_CARDS = [
  "Workflow Runs",
  "AI Credits",
  "Outputs",
  "Research Lookups",
  "Voice Minutes",
  "API Calls",
]

async function main() {
  await mkdir(OUT, { recursive: true })
  const browser = await chromium.launch()
  const failures = []

  for (const scheme of ["light", "dark"]) {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 2200 },
      deviceScaleFactor: 2,
      colorScheme: scheme,
    })
    const page = await context.newPage()

    const response = await page.goto(URL, { waitUntil: "networkidle" })
    if (response && response.status() !== 200) {
      failures.push(`${scheme}: page returned ${response.status()}`)
    }

    // The harness applies theme via a class on <html>, so set it explicitly
    // rather than trusting colorScheme alone to drive Tailwind's dark variant.
    await page.emulateMedia({ colorScheme: scheme })
    await page.evaluate((s) => {
      document.documentElement.classList.toggle("dark", s === "dark")
    }, scheme)

    await page.waitForTimeout(1200) // usage bars and count-up animate in

    const body = await page.evaluate(() => document.body.innerText)

    // Grid completeness: all six cards must be present as one set.
    for (const name of EXPECTED_CARDS) {
      if (!body.includes(name)) failures.push(`${scheme}: missing usage card "${name}"`)
    }

    // Part A: API Calls must NOT advertise a fabricated allowance.
    if (!body.includes("Metered")) {
      failures.push(`${scheme}: API Calls is not showing its Metered chip`)
    }
    if (body.includes("/ 500,000")) {
      failures.push(`${scheme}: API Calls still prints the fabricated 500,000 denominator`)
    }

    // Part C: auto top-up must state the real configured numbers and the cap.
    for (const phrase of ["When Voice Minutes drop below", "Hard cap", "Prepaid balance"]) {
      if (!body.includes(phrase)) failures.push(`${scheme}: auto top-up missing "${phrase}"`)
    }

    await page.screenshot({ path: `${OUT}/billing-usage-${scheme}.png`, fullPage: true })

    // Part B: open the Add Minutes modal and prove the real prices render.
    const addMinutes = page.getByRole("button", { name: "Add Minutes" })
    if ((await addMinutes.count()) === 0) {
      failures.push(`${scheme}: Add Minutes button not found (voice block did not render)`)
    } else {
      await addMinutes.first().click()
      const dialog = page.getByRole("dialog")
      await dialog.waitFor({ state: "visible", timeout: 5000 })
      const dialogText = await dialog.innerText()

      // 60 / 300 / 1200 at $0.12 -> $7.20 / $36.00 / $144.00. Asserting the
      // computed dollar amounts, not just the minute counts, is the point:
      // minute labels would still pass if the price math rendered as NaN.
      for (const amount of ["$7.20", "$36.00", "$144.00"]) {
        if (!dialogText.includes(amount)) {
          failures.push(`${scheme}: modal missing real price ${amount}`)
        }
      }
      if (dialogText.includes("NaN") || dialogText.includes("$undefined")) {
        failures.push(`${scheme}: modal price math produced NaN/undefined`)
      }

      // Exactly one pack selected by default — the same silent-selection bug
      // class that got past a text-only check on the voice comp.
      const selected = await dialog.getByRole("radio", { checked: true }).count()
      if (selected !== 1) {
        failures.push(`${scheme}: expected exactly 1 selected pack, found ${selected}`)
      }

      await page.screenshot({ path: `${OUT}/add-minutes-modal-${scheme}.png` })
    }

    await context.close()
  }

  await browser.close()

  if (failures.length > 0) {
    console.error("[capture-billing-states] FAILED:")
    for (const f of failures) console.error(`  - ${f}`)
    process.exit(1)
  }
  console.log(`[capture-billing-states] OK — wrote 4 screenshots to ${OUT}/`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
