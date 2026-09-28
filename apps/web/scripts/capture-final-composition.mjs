// Final-composition capture: dashboard density, Measure region, agent detail
// composition, connectors no-selection summary vs selected inspector. Harness
// routes (/e2e/shots/*) render fixture data only; they are not owner-live evidence.
// Usage: node scripts/capture-final-composition.mjs <outDir> [base] [--before]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { chromium } from "@playwright/test"

const OUT = process.argv[2]
const BASE = process.argv[3] && !process.argv[3].startsWith("--") ? process.argv[3] : "http://127.0.0.1:3010"
const BEFORE = process.argv.includes("--before")
const BUILD_ID = readFileSync(join(process.cwd(), ".next/BUILD_ID"), "utf8").trim()
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({
  executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
})
const VIEW = {
  d1440: [1440, 900],
  d1920: [1920, 1080],
  tall: [1440, 2200],
  tablet: [1024, 1600],
  mobile: [390, 2000],
}
const results = []

async function shot(name, { path, viewport, theme = "light", action, element, cls }) {
  const [width, height] = VIEW[viewport]
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: theme, deviceScaleFactor: 1 })
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem("gravitre-app-theme", t)
      localStorage.setItem("gravitre-welcome-dismissed", "true")
    } catch {}
  }, theme)
  const page = await ctx.newPage()
  const errors = []
  page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 200)))
  try {
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 120000 })
    await page.waitForTimeout(4000)
    const note = action ? (await action(page)) || "" : ""
    const file = `${name}.png`
    if (element) {
      const target = page.locator(element).first()
      await target.scrollIntoViewIfNeeded()
      await page.waitForTimeout(600)
      await target.screenshot({ path: join(OUT, file) })
    } else {
      await page.screenshot({ path: join(OUT, file) })
    }
    const metrics = await page.evaluate(() => {
      const flow = document.querySelector("[data-operating-flow] > div:nth-child(2)")
      const measure = document.querySelector("#dashboard-measure")
      return {
        flowHeight: flow ? Math.round(flow.getBoundingClientRect().height) : null,
        measureTop: measure ? Math.round(measure.getBoundingClientRect().top) : null,
        hScroll: document.documentElement.scrollWidth > window.innerWidth + 1,
      }
    })
    results.push({ name, file, route: path, viewport: `${width}x${height}`, theme, class: cls, note, ...metrics, consoleErrors: errors.slice(0, 5) })
    console.log("ok", name, JSON.stringify(metrics))
  } catch (e) {
    results.push({ name, route: path, viewport, theme, error: String(e).slice(0, 300) })
    console.log("FAIL", name, String(e).slice(0, 300))
  } finally {
    await ctx.close()
  }
}

const H = { path: "/e2e/shots/home", cls: "fixture harness (dashboard, ops-summary fixture)" }
const AD = { path: "/e2e/shots/agent-detail", cls: "fixture harness (agent detail, identity + capabilities fixtures)" }
const C = { path: "/e2e/shots/connectors", cls: "fixture harness (connectors)" }
const selectRow = async (p) => {
  const row = p.locator("[data-gravitre-connector-row]").first()
  await row.scrollIntoViewIfNeeded()
  await row.click({ position: { x: 60, y: 20 } })
  await p.waitForTimeout(1200)
}
const tag = BEFORE ? "before" : "after"

await shot(`dashboard-1440x900-light-${tag}`, { ...H, viewport: "d1440" })
await shot(`dashboard-1920x1080-light-${tag}`, { ...H, viewport: "d1920" })
await shot(`dashboard-1920x1080-dark-${tag}`, { ...H, viewport: "d1920", theme: "dark" })
await shot(`agent-detail-1440-tall-light-${tag}`, { ...AD, viewport: "tall" })
await shot(`connectors-1440-noselection-light-${tag}`, { ...C, viewport: "d1440", element: '[data-review-surface="connectors-management"]' })

if (!BEFORE) {
  await shot("dashboard-measure-light", { ...H, viewport: "d1440", element: '[aria-labelledby="dashboard-measure"]' })
  await shot("dashboard-measure-dark", { ...H, viewport: "d1440", theme: "dark", element: '[aria-labelledby="dashboard-measure"]' })
  await shot("dashboard-tablet-light", { ...H, viewport: "tablet" })
  await shot("dashboard-mobile-light", { ...H, viewport: "mobile" })
  await shot("agent-detail-1440-tall-dark", { ...AD, viewport: "tall", theme: "dark" })
  await shot("agent-detail-1920x1080-light", { ...AD, viewport: "d1920" })
  await shot("agent-detail-tablet-light", { ...AD, viewport: "tablet" })
  await shot("agent-detail-mobile-light", { ...AD, viewport: "mobile" })
  await shot("connectors-1440-tall-noselection-light", { ...C, viewport: "tall", element: '[data-review-surface="connectors-management"]' })
  await shot("connectors-1440-tall-noselection-dark", { ...C, viewport: "tall", theme: "dark", element: '[data-review-surface="connectors-management"]' })
  await shot("connectors-1440-tall-selected-light", { ...C, viewport: "tall", action: selectRow, element: '[data-review-surface="connectors-management"]' })
  await shot("connectors-1440-tall-selected-dark", { ...C, viewport: "tall", theme: "dark", action: selectRow, element: '[data-review-surface="connectors-management"]' })
  await shot("connectors-1920x1080-light", { ...C, viewport: "d1920" })
  await shot("connectors-tablet-light", { ...C, viewport: "tablet" })
}

writeFileSync(join(OUT, "manifest.json"), JSON.stringify({ base: BASE, buildId: BUILD_ID, at: new Date().toISOString(), results }, null, 2))
await browser.close()
