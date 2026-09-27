// Local review probe: distance from each builder edge endpoint to the nearest
// handle centre on the fixture harness (/e2e/shots/builder). No backend.
// Usage: node scripts/probe-builder-edges.mjs [base] [--debug]
import { chromium } from "playwright-core"

const BASE = process.argv[2] || "http://127.0.0.1:3010"
const DEBUG = process.argv.includes("--debug")
const browser = await chromium.launch({
  executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
})
for (const [name, width, height] of [
  ["desktop", 1440, 900],
  ["tablet", 1024, 768],
  ["mobile", 390, 844],
]) {
  const ctx = await browser.newContext({ viewport: { width, height } })
  const page = await ctx.newPage()
  await page.goto(`${BASE}/e2e/shots/builder`, { waitUntil: "domcontentloaded", timeout: 120000 })
  await page.waitForSelector("[data-canvas-node]", { timeout: 60000 })
  await page.waitForTimeout(2500)
  const out = await page.evaluate((debug) => {
    const centre = (r) => [r.left + r.width / 2, r.top + r.height / 2]
    const handles = [...document.querySelectorAll("[data-canvas-node] [data-connect-state]")].map((h) => ({
      node: h.closest("[data-canvas-node]").dataset.canvasNode,
      c: centre(h.getBoundingClientRect()),
    }))
    const dots = [...document.querySelectorAll('g.connection-group > circle[r="3"]')].map((c) => centre(c.getBoundingClientRect()))
    const offsets = dots.map(([x, y]) => {
      let best = { d: Infinity, node: "" }
      for (const h of handles) {
        const d = Math.hypot(h.c[0] - x, h.c[1] - y)
        if (d < best.d) best = { d, node: h.node }
      }
      return { d: Math.round(best.d * 10) / 10, node: best.node, at: [Math.round(x), Math.round(y)] }
    })
    const nodes = debug
      ? [...document.querySelectorAll("[data-canvas-node]")].map((el) => {
          const s = el.querySelector("[data-node-surface]")
          const r = (s ?? el).getBoundingClientRect()
          return { id: el.dataset.canvasNode, surface: Boolean(s), rect: [r.left, r.top, r.width, r.height].map(Math.round) }
        })
      : []
    return { offsets, nodes }
  }, DEBUG)
  const ds = out.offsets.map((o) => o.d)
  console.log(name, `endpoints=${ds.length}`, `max=${Math.max(...ds).toFixed(1)}`)
  if (DEBUG) console.log(JSON.stringify(out, null, 0))
  await ctx.close()
}
await browser.close()
