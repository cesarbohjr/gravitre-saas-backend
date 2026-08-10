/**
 * Captures the voice UI design-review comp (/e2e/shots/voice-states) in both
 * themes at desktop plus a mobile width.
 *
 * Runs in the project sandbox, so it can reach the local dev server directly —
 * the agent-browser sandbox cannot be relied on to route localhost.
 *
 * Usage: node scripts/capture-voice-states.mjs
 */
import { chromium } from "@playwright/test"
import { mkdir } from "node:fs/promises"

const BASE = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"
const URL = `${BASE}/e2e/shots/voice-states`
const OUT = "/tmp/agent-browser"

const VIEWPORTS = [
  { tag: "desktop", width: 1440, height: 1180 },
  { tag: "mobile", width: 414, height: 1200 },
]

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch()

for (const scheme of ["light", "dark"]) {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      colorScheme: scheme,
      deviceScaleFactor: 2,
    })
    const page = await context.newPage()

    const errors = []
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text())
    })
    page.on("pageerror", (e) => errors.push(String(e)))

    await page.goto(URL, { waitUntil: "networkidle" })
    // The theme provider reads a stored preference, so force the class directly
    // rather than trusting colorScheme alone.
    await page.evaluate((s) => {
      document.documentElement.classList.toggle("dark", s === "dark")
    }, scheme)

    // Assert on text only the real components can produce.
    // Live-floor pills use speaker names (11a/11b): You / agentLabel — not
    // "Listening" / "Agent speaking".
    await page.getByText("You", { exact: true }).first().waitFor({ timeout: 20000 })
    await page.getByText("Gravitre", { exact: true }).first().waitFor({ timeout: 20000 })
    await page.getByText("Voice paused — credits needed").first().waitFor({ timeout: 20000 })
    // Preset cards prove the /api/voice/library fixture resolved.
    await page.getByText("Atlas").first().waitFor({ timeout: 20000 })

    // A fixture missing voice_id still renders four cards but keys them all on
    // undefined and selects none, which a text-only assertion would pass. Fail
    // loudly on that instead: exactly one preset card must read as selected.
    // Scoped to the voice names, because the modality toggle and the
    // preset/custom tabs also expose aria-pressed.
    const selected = await page
      .locator('[aria-pressed="true"]')
      .filter({ hasText: /Atlas|Juno|Cormac|Sable/ })
      .count()
    if (selected !== 1) {
      throw new Error(
        `expected exactly 1 selected preset card, found ${selected} — check the voice fixture's voice_id`,
      )
    }

    // Let the waveform loops reach a non-zero frame before freezing them, so the
    // capture does not show every bar at rest.
    await page.waitForTimeout(900)

    const file = `${OUT}/voice-states-${scheme}-${vp.tag}.png`
    await page.screenshot({ path: file, fullPage: true })

    // Measure the tokens that matter: the mic must not be red, and the billing
    // strip must be amber rather than destructive.
    if (vp.tag === "desktop") {
      const probe = await page.evaluate(() => {
        const read = (text) => {
          const el = [...document.querySelectorAll("div")].find(
            (d) =>
              d.getAttribute("role") === "status" &&
              d.textContent?.trim().startsWith(text) &&
              (d.className.includes("rounded-full") || d.className.includes("rounded-lg")),
          )
          return el ? getComputedStyle(el).borderColor : null
        }
        return {
          billing: read("Voice paused"),
          listening: read("You"),
        }
      })
      console.log(`  tokens ${scheme}:`, JSON.stringify(probe))
    }

    console.log(
      `${scheme}/${vp.tag} -> ${file}${errors.length ? ` (console errors: ${errors.length})` : ""}`,
    )
    if (errors.length) console.log("   ", errors.slice(0, 3).join(" | "))

    await context.close()
  }
}

await browser.close()
