// Capture /e2e/shots/<name> harness surfaces at phone and desktop sizes and
// report render errors, horizontal overflow and sub-44px touch targets.
// Fixture data only; not owner-live evidence.
// Usage: node scripts/audit-shot-surfaces.mjs <outDir> <tag> <name...>
import { mkdirSync } from "node:fs"
import { join } from "node:path"

async function loadChromium() {
  for (const spec of ["@playwright/test", "playwright", "/tmp/pw/node_modules/playwright/index.mjs"]) {
    try {
      const mod = await import(spec)
      return mod.chromium ?? mod.default?.chromium
    } catch {}
  }
  throw new Error("Playwright is not installed")
}

const [OUT = "/tmp/agent-browser", TAG = "shot", ...NAMES] = process.argv.slice(2)
const BASE = process.env.SHOT_BASE ?? "http://localhost:3000"
mkdirSync(OUT, { recursive: true })

const chromium = await loadChromium()
const browser = await chromium.launch({ headless: true })

for (const name of NAMES) {
  for (const [size, width, height] of [
    ["m", 390, 844],
    ["d", 907, 797],
  ]) {
    const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: "dark" })
    await ctx.addInitScript(() => {
      try {
        localStorage.setItem("gravitre-app-theme", "dark")
        localStorage.setItem("gravitre-welcome-dismissed", "true")
      } catch {}
    })
    const page = await ctx.newPage()
    const errors = []
    page.on("pageerror", (e) => errors.push(String(e.message).slice(0, 200)))
    page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 160)))
    const res = await page.goto(`${BASE}/e2e/shots/${name}`, { waitUntil: "domcontentloaded", timeout: 120000 })
    await page.waitForTimeout(7000)
    const report = await page.evaluate(() => {
      const text = document.body.innerText
      const targets = [
        ...document.querySelectorAll(
          "main button, main a, main [role=tab], main [role=switch], main [role=checkbox], main input, main select, main textarea",
        ),
      ]
      return {
        failed: (text.match(/(Something went wrong|could not be found|Application error)[^\n]*/) || [""])[0],
        literalNewline: text.includes("\\n"),
        overflowX: document.documentElement.scrollWidth > window.innerWidth,
        wide: [...document.querySelectorAll("main *")]
          .filter((e) => {
            const r = e.getBoundingClientRect()
            return r.width > 0 && r.right > window.innerWidth + 2 && !e.closest("[class*='overflow-x']")
          })
          .slice(0, 5)
          .map((e) => `${e.tagName}.${String(e.className).slice(0, 60)}`),
        headings: [...document.querySelectorAll("main h1, main h2, main h3")]
          .map((e) => e.textContent.trim().slice(0, 40))
          .slice(0, 14),
        small: targets
          .filter((e) => {
            const r = e.getBoundingClientRect()
            return r.height > 0 && r.width > 0 && r.height < 44 && getComputedStyle(e).visibility !== "hidden"
          })
          .map(
            (e) =>
              `${(e.getAttribute("aria-label") || e.textContent.trim() || e.getAttribute("placeholder") || e.tagName).slice(0, 24)}:${Math.round(e.getBoundingClientRect().height)}`,
          )
          .slice(0, 30),
      }
    })
    const file = join(OUT, `${name}-${TAG}-${size}.png`)
    await page.screenshot({ path: file, fullPage: size === "m" })
    console.log(JSON.stringify({ name, size, status: res?.status(), file, ...report, errors: errors.slice(0, 4) }))
    await ctx.close()
  }
}

await browser.close()
