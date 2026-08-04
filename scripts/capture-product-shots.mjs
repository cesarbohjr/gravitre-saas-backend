/**
 * Captures product screenshots for the marketing site from the real app
 * surfaces rendered by /e2e/shots/<view>.
 *
 * Runs Playwright inside the PROJECT sandbox, which is the only place that can
 * reach the local dev server. (The agent-browser tool runs in a separate
 * sandbox where `localhost` resolves to the production domain, so screenshots
 * taken there silently capture prod instead of local code.)
 *
 *   node scripts/capture-product-shots.mjs [--probe] [--only <view>]
 */
// The repo depends on @playwright/test, which re-exports the browser types;
// bare "playwright" is not resolvable here.
import { chromium } from "@playwright/test"
import { mkdir } from "node:fs/promises"
import { join } from "node:path"

const BASE = process.env.SHOT_BASE_URL ?? "http://localhost:3000"
const OUT = join(process.cwd(), "apps/web/public/product")
const SCALE = 2

const args = process.argv.slice(2)
const probeOnly = args.includes("--probe")
const onlyIdx = args.indexOf("--only")
const only = onlyIdx !== -1 ? args[onlyIdx + 1] : null

/** Each shot targets a real surface; `wait` is copy that proves data arrived. */
const SHOTS = [
  { name: "app-activity", view: "activity", wait: "Northwind", width: 1440, height: 900 },
  { name: "app-approvals", view: "approvals", wait: "Northwind", width: 1440, height: 900 },
  { name: "app-connectors", view: "connectors", wait: "HubSpot", width: 1440, height: 900 },
]

async function probe(page) {
  const res = await page.goto(`${BASE}/shot-bridge-probe.txt`, { waitUntil: "domcontentloaded" })
  const host = new URL(page.url()).host
  const body = (await page.textContent("body")) ?? ""
  const ok = host.startsWith("localhost") && body.includes("shot-bridge-probe")
  console.log(`probe: status=${res?.status()} host=${host} ok=${ok}`)
  if (!ok) {
    console.error(
      "ABORT: not reaching the local dev server (requests are escaping to another origin)."
    )
  }
  return ok
}

const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SCALE })

  const errors = []
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text().slice(0, 160))
  })

  if (!(await probe(page))) process.exit(1)
  if (probeOnly) process.exit(0)

  await mkdir(OUT, { recursive: true })
  let failed = 0

  for (const shot of SHOTS) {
    if (only && shot.view !== only) continue
    const url = `${BASE}/e2e/shots/${shot.view}`
    await page.setViewportSize({ width: shot.width, height: shot.height })
    await page.goto(url, { waitUntil: "networkidle" })

    try {
      // Proves real data rendered, rather than a spinner or empty state.
      await page.getByText(shot.wait, { exact: false }).first().waitFor({ timeout: 20_000 })
    } catch {
      const text = ((await page.textContent("body")) ?? "").replace(/\s+/g, " ").trim()
      console.error(`FAIL ${shot.name}: never found ${JSON.stringify(shot.wait)}`)
      console.error(`  body: ${text.slice(0, 240)}`)
      failed++
      continue
    }

    await page.waitForTimeout(700)
    await page.screenshot({ path: join(OUT, `${shot.name}.png`) })
    console.log(`ok   ${shot.name}.png`)
  }

  if (errors.length) {
    console.log(`\nconsole errors (${errors.length}):`)
    ;[...new Set(errors)].slice(0, 8).forEach((e) => console.log(`  ${e}`))
  }

  if (failed) {
    console.error(`\n${failed} shot(s) failed`)
    process.exit(1)
  }
} finally {
  await browser.close()
}
