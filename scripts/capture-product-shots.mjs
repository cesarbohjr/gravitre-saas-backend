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
  // "103" is the tasks-today tally summed across the four fixture agents
  // (34+12+57+0). A derived number like this cannot be produced by the empty
  // state or by static chrome, so it proves the list actually hydrated.
  { name: "app-agents", view: "agents", wait: "103", width: 1440, height: 900 },
  // Not a workflow name: several appear in static marketing-ish copy elsewhere
  // on the page. "98.2%" is a fixture-only successRate string, and because the
  // page renders it verbatim it also proves the value survived normalisation
  // with its percent sign intact.
  { name: "app-workflows", view: "workflows", wait: "98.2%", width: 1440, height: 900 },
  // A conversation title from the history sidebar — the part that was silently
  // rendering "No conversations yet" until /api/conversations was fixtured.
  //
  // `prepare` opens that sidebar first. It defaults to closed (useState(false),
  // no persistence), and when closed the desktop styles are `md:w-0
  // md:overflow-hidden` — so every conversation title is present in the DOM at
  // zero width. A naive text assertion passes while the screenshot shows no
  // history at all; only .waitFor()'s visibility check catches it.
  {
    name: "app-ai",
    view: "ai",
    wait: "Why did the Salesforce write get blocked?",
    width: 1440,
    height: 900,
    prepare: async (page) => {
      await page.getByRole("button", { name: "Show history" }).click()
    },
  },
]

/**
 * CSS that hides the Next.js/Turbopack dev overlay, which otherwise bakes a red
 * "N Issues" badge into the bottom-left of every marketing screenshot.
 *
 * Hide the `nextjs-portal` host rather than clicking the toast or removing the
 * node. Clicking is actively dangerous here: the toast's first descendant
 * button EXPANDS the full-screen error panel instead of dismissing it, which
 * silently replaced an entire screenshot with a stack trace while every text
 * assertion still passed. Removing the node is also discouraged, since that
 * portal hosts dev overlay styles (see verify-chat-backgrounds.mjs).
 *
 * The underlying warning comes from the harness's own bootstrap <script> in
 * app/e2e/shots/layout.tsx — dev-only scaffolding that never ships to users, so
 * it is suppressed here rather than restructured.
 */
const HIDE_DEV_OVERLAY = `
  nextjs-portal,
  [data-nextjs-toast],
  [data-nextjs-dev-tools-button] { display: none !important; }
`

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
      // Some surfaces need an interaction before the payload is on screen.
      if (shot.prepare) {
        await shot.prepare(page)
        // Sidebar/panel transitions are 300ms; let them settle before asserting
        // visibility or the width check races the animation.
        await page.waitForTimeout(600)
      }
      // Proves real data rendered, rather than a spinner or empty state.
      // .waitFor() also requires a non-zero box, which is what catches content
      // that hydrated inside a collapsed container.
      await page.getByText(shot.wait, { exact: false }).first().waitFor({ timeout: 20_000 })
    } catch {
      const text = ((await page.textContent("body")) ?? "").replace(/\s+/g, " ").trim()
      console.error(`FAIL ${shot.name}: never found ${JSON.stringify(shot.wait)}`)
      console.error(`  body: ${text.slice(0, 240)}`)
      failed++
      continue
    }

    await page.waitForTimeout(700)
    // Last thing before the shutter: the overlay can appear late, after the data
    // assertion above has already passed. addStyleTag is per-document, so it has
    // to be re-applied after each navigation rather than set up once.
    await page.addStyleTag({ content: HIDE_DEV_OVERLAY }).catch(() => {})
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
