/**
 * Capture /e2e/shots/voice-states for design review.
 * Asserts on tokens only the real components can produce.
 */
import { chromium, devices } from "playwright"
import { mkdirSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const OUT = join(ROOT, "docs/delivery/shots/voice-ui")
const URL = process.env.VOICE_SHOTS_URL || "http://127.0.0.1:3000/e2e/shots/voice-states"

mkdirSync(OUT, { recursive: true })

const viewports = [
  { tag: "desktop", ...devices["Desktop Chrome"] },
]

const schemes = ["light", "dark"]

const browser = await chromium.launch()
for (const scheme of schemes) {
  for (const vp of viewports) {
    const context = await browser.newContext({
      ...vp,
      colorScheme: scheme,
    })
    const page = await context.newPage()
    const errors = []
    page.on("pageerror", (err) => errors.push(String(err)))

    await page.goto(URL, { waitUntil: "networkidle" })
    await page.evaluate((s) => {
      document.documentElement.classList.toggle("dark", s === "dark")
    }, scheme)

    // In-input pills: idle + You + Gravitre (11a/11b).
    await page.getByText("You", { exact: true }).first().waitFor({ timeout: 20000 })
    await page.getByText("Gravitre", { exact: true }).first().waitFor({ timeout: 20000 })
    await page.getByText("Ask, delegate, or search…").first().waitFor({ timeout: 20000 })
    await page.getByText("Atlas").first().waitFor({ timeout: 20000 })

    const selected = await page
      .locator('[aria-pressed="true"]')
      .filter({ hasText: /Atlas|Juno|Cormac|Sable/ })
      .count()
    if (selected !== 1) {
      throw new Error(
        `expected exactly 1 selected preset card, found ${selected} — check the voice fixture's voice_id`,
      )
    }

    await page.waitForTimeout(900)

    const file = `${OUT}/voice-states-${scheme}-${vp.tag}.png`
    await page.screenshot({ path: file, fullPage: true })
    console.log(
      `${scheme}/${vp.tag} -> ${file}${errors.length ? ` (console errors: ${errors.length})` : ""}`,
    )
    if (errors.length) console.log("   ", errors.slice(0, 3).join(" | "))

    await context.close()
  }
}
await browser.close()
