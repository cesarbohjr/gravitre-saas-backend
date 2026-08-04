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
const PROBE_PATH = "/e2e/shots/activity"
const OUT = join(process.cwd(), "apps/web/public/product")
const SCALE = 2

const args = process.argv.slice(2)
const probeOnly = args.includes("--probe")
const onlyIdx = args.indexOf("--only")
const only = onlyIdx !== -1 ? args[onlyIdx + 1] : null

/** Each shot targets a real surface; `wait` is copy that proves data arrived. */
const SHOTS = [
  { name: "app-activity", view: "activity", wait: "Northwind", width: 1440, height: 900 },
  // Not "Northwind": the approvals queue renders request titles, not the org name.
  // ?id= deep-links a request so the detail pane is populated instead of showing
  // a half-empty "Select a request to view details" placeholder.
  {
    name: "app-approvals",
    view: "approvals",
    query: "?id=apr_01hq9d4k2m",
    wait: "Priya Raman",
    width: 1440,
    height: 900,
  },
  // Not "HubSpot": that name also appears in the always-present "available
  // connectors" catalog, so it matched even when zero connectors were loaded.
  // "3 connected" can only come from the fixture data — 3, not 4, because the
  // Salesforce row is deliberately in `error` state and is excluded from the
  // connected tally.
  { name: "app-connectors", view: "connectors", wait: "3 connected", width: 1440, height: 900 },
]

/**
 * Confirms we are really talking to the local dev server.
 *
 * Probe a real PAGE route, not a static .txt: proxy.ts's matcher only excludes
 * svg/png/css/js/etc, so an unauthenticated .txt request is treated as a
 * protected page and 307s to the production login URL. That looks identical to
 * a broken sandbox bridge and sent me chasing the wrong bug.
 */
async function probe(page) {
  const res = await page.goto(`${BASE}${PROBE_PATH}`, { waitUntil: "domcontentloaded" })
  const host = new URL(page.url()).host
  const expected = new URL(BASE).host
  const ok = res?.status() === 200 && host === expected
  console.log(`probe: status=${res?.status()} host=${host} expected=${expected} ok=${ok}`)
  if (!ok) {
    console.error(
      `ABORT: expected ${expected} but landed on ${host} — requests are escaping to another origin.`
    )
  }
  return ok
}

const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SCALE })

  // top-bar reads the org from localStorage in a useState initializer, so the
  // value must exist before ANY page script runs or it renders the hardcoded
  // "Acme Corp" default. The layout's own seed is too late for that first paint.
  await page.addInitScript(() => {
    localStorage.setItem(
      "gravitre:selectedOrg",
      // Must match DEMO_ORG_ID in lib/e2e-shot-fixtures.ts.
      JSON.stringify({ id: "00000000-0000-0000-0000-000000000001", name: "Northwind Logistics" })
    )
    localStorage.setItem("gravitre-welcome-dismissed", "true")
  })

  const errors = []
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text().slice(0, 160))
  })

  if (!(await probe(page))) process.exit(1)
  if (probeOnly) process.exit(0)

  // --debug dumps rendered text + uncaught errors for one view. textContent()
  // includes inline <script> source, which makes failures look like gibberish;
  // innerText shows only what is actually visible.
  if (args.includes("--debug")) {
    const view = only ?? "approvals"
    const pageErrors = []
    page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 300)))
    await page.goto(`${BASE}/e2e/shots/${view}`, { waitUntil: "networkidle" })
    await page.waitForTimeout(7000)
    // Ask the page directly what the interceptor returns. Do NOT try to diagnose
    // this by listening for Playwright request events: the harness patches
    // window.fetch and answers from fixtures before anything reaches the
    // network, so "0 /api/* requests" is always true and proves nothing.
    const diag = await page.evaluate(async () => {
      const out = { storedOrg: localStorage.getItem("gravitre:selectedOrg") }
      for (const p of ["/api/organizations", "/api/connectors?org=x"]) {
        try {
          const r = await fetch(p)
          out[p] = `${r.status} ${(await r.text()).slice(0, 100)}`
        } catch (e) {
          out[p] = `THREW ${String(e).slice(0, 100)}`
        }
      }
      return out
    })
    console.log("diagnostics:")
    for (const [k, v] of Object.entries(diag)) console.log(`  ${k}: ${v}`)

    const visible = await page.evaluate(() => document.body.innerText)
    console.log(`landed on: ${new URL(page.url()).pathname}`)
    console.log(`visible text (${visible.length} chars):`)
    console.log(visible.slice(0, 600))
    if (pageErrors.length) {
      console.log("page errors:")
      pageErrors.slice(0, 5).forEach((e) => console.log(`  ${e}`))
    }
    if (errors.length) {
      console.log("console errors:")
      ;[...new Set(errors)].slice(0, 8).forEach((e) => console.log(`  ${e}`))
    }
    process.exit(0)
  }

  await mkdir(OUT, { recursive: true })
  let failed = 0

  for (const shot of SHOTS) {
    if (only && shot.view !== only) continue
    const url = `${BASE}/e2e/shots/${shot.view}${shot.query ?? ""}`
    await page.setViewportSize({ width: shot.width, height: shot.height })
    await page.goto(url, { waitUntil: "networkidle" })
    // The layout seeds gravitre:selectedOrg on first paint, but top-bar reads it
    // in a useState initializer, so the first render can still show the "Acme
    // Corp" default. Reload once so it hydrates from the seeded value.
    await page.reload({ waitUntil: "networkidle" })

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
