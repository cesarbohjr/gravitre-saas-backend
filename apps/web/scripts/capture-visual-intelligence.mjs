// Visual-intelligence pass capture: connectors, agents, agent detail, dashboard
// outcome flow, builder node family, AI-native board. Harness routes
// (/e2e/shots/*) render fixture data only; /dev/carbon-board is placeholder.
// Usage: node scripts/capture-visual-intelligence.mjs <outDir> [base] [--before]
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { chromium } from "@playwright/test"

const OUT = process.argv[2]
const BASE = process.argv[3] || "http://127.0.0.1:3010"
const BEFORE = process.argv.includes("--before")
const BUILD_ID = readFileSync(join(process.cwd(), ".next/BUILD_ID"), "utf8").trim()
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({
  executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
})
const VIEW = { desktop: [1440, 900], tall: [1440, 1800], tablet: [1024, 1400], mobile: [390, 1600] }
const results = []

async function open(path, viewport, theme, waitSel) {
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
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 120000 })
  if (waitSel) await page.waitForSelector(waitSel, { timeout: 60000 })
  await page.waitForTimeout(3500)
  return { ctx, page, errors }
}

async function shot(name, { path, viewport = "tall", theme = "light", waitSel, action, cls, element }) {
  const { ctx, page, errors } = await open(path, viewport, theme, waitSel)
  try {
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
    const hScroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    results.push({ name, file, route: path, viewport, theme, class: cls, note, hScroll, consoleErrors: errors.slice(0, 5) })
    console.log("ok", name)
  } catch (e) {
    results.push({ name, route: path, viewport, theme, error: String(e).slice(0, 300) })
    console.log("FAIL", name, String(e).slice(0, 300))
  } finally {
    await ctx.close()
  }
}

const C = { path: "/e2e/shots/connectors", cls: "fixture harness (connectors)" }
const A = { path: "/e2e/shots/agents", cls: "fixture harness (agents)" }
const AD = { path: "/e2e/shots/agent-detail", cls: "fixture harness (agent detail, identity + capabilities fixtures)" }
const H = { path: "/e2e/shots/home", cls: "fixture harness (dashboard, ops-summary fixture)" }
const B = { path: "/e2e/shots/builder", waitSel: '[data-review-surface="workflow-identity"]', cls: "fixture harness (builder seed graph)" }

const selectRow = async (p) => {
  const row = p.locator("[data-gravitre-connector-row]").first()
  await row.scrollIntoViewIfNeeded()
  await row.click({ position: { x: 60, y: 20 } })
  await p.waitForTimeout(1200)
}

if (BEFORE) {
  await shot("dashboard-before-light", { ...H })
  await shot("agent-detail-before-light", { ...AD })
  await shot("agent-detail-before-dark", { ...AD, theme: "dark" })
} else {
  // Connectors
  await shot("connectors-light", { ...C })
  await shot("connectors-dark", { ...C, theme: "dark" })
  await shot("connectors-discovery-light", { ...C, element: '[data-review-surface="connectors-discovery"]' })
  await shot("connectors-discovery-dark", { ...C, theme: "dark", element: '[data-review-surface="connectors-discovery"]' })
  await shot("connectors-list-light", { ...C, element: '[data-review-surface="connectors-management"]' })
  await shot("connectors-inspector-light", { ...C, action: selectRow, element: '[data-review-surface="connectors-management"]' })
  await shot("connectors-inspector-dark", { ...C, theme: "dark", action: selectRow, element: '[data-review-surface="connectors-management"]' })
  await shot("connectors-tablet-light", { ...C, viewport: "tablet" })
  await shot("connectors-mobile-light", { ...C, viewport: "mobile" })

  // Agents
  await shot("agents-roster-light", { ...A, viewport: "desktop" })
  await shot("agents-roster-dark", { ...A, theme: "dark", viewport: "desktop" })
  await shot("agent-detail-light", { ...AD })
  await shot("agent-detail-dark", { ...AD, theme: "dark" })
  await shot("agent-autonomy-light", { ...AD, element: '[data-review-surface="agent-autonomy"]' })
  await shot("agent-autonomy-dark", { ...AD, theme: "dark", element: '[data-review-surface="agent-autonomy"]' })
  await shot("agent-detail-mobile-light", { ...AD, viewport: "mobile" })

  // Dashboard
  await shot("dashboard-light", { ...H })
  await shot("dashboard-dark", { ...H, theme: "dark" })
  await shot("dashboard-outcome-flow-light", { ...H, element: '[data-review-surface="outcome-flow"]' })
  await shot("dashboard-outcome-flow-dark", { ...H, theme: "dark", element: '[data-review-surface="outcome-flow"]' })
  await shot("dashboard-tablet-light", { ...H, viewport: "tablet" })
  await shot("dashboard-mobile-light", { ...H, viewport: "mobile" })

  // Builder node family
  const clickNode = (id) => async (p) => {
    const box = await p.locator(`[data-canvas-node="${id}"]`).first().boundingBox()
    if (!box) throw new Error(`node not found: ${id}`)
    await p.mouse.click(box.x + box.width / 2, box.y + 16)
    await p.waitForTimeout(900)
  }
  await shot("builder-light", { ...B, viewport: "desktop" })
  await shot("builder-dark", { ...B, theme: "dark", viewport: "desktop" })
  await shot("builder-council-selected-light", { ...B, action: clickNode("node-6"), viewport: "desktop" })
  await shot("builder-council-selected-dark", { ...B, theme: "dark", action: clickNode("node-6"), viewport: "desktop" })
  await shot("builder-decision-selected-light", { ...B, action: clickNode("node-7"), viewport: "desktop" })
  await shot("builder-tablet-light", { ...B, viewport: "tablet" })
  await shot("builder-mobile-light", { ...B, viewport: "mobile" })
  for (const theme of ["light", "dark"]) {
    const { ctx, page } = await open(B.path, "desktop", theme, B.waitSel)
    try {
      for (const [id, label] of [
        ["node-1", "source"],
        ["node-2", "agent"],
        ["node-3", "task"],
        ["node-7", "decision"],
        ["node-6", "council"],
        ["node-4", "approval"],
        ["node-5", "connector"],
      ]) {
        const inner = await page.locator(`[data-canvas-node="${id}"] > div`).first().boundingBox()
        if (!inner) throw new Error(`crop target missing: ${id}`)
        const pad = 24
        await page.screenshot({
          path: join(OUT, `node-${label}-${theme}.png`),
          clip: { x: Math.max(0, inner.x - pad), y: Math.max(0, inner.y - pad), width: inner.width + pad * 2, height: inner.height + pad * 2 },
        })
        results.push({ name: `node-${label}-${theme}`, file: `node-${label}-${theme}.png`, route: B.path, viewport: "desktop", theme, class: B.cls })
      }
      console.log("ok node crops", theme)
    } catch (e) {
      console.log("FAIL node crops", theme, String(e).slice(0, 200))
    } finally {
      await ctx.close()
    }
  }

  // AI-native board section (internal /dev route, placeholder content)
  for (const theme of ["light", "dark"]) {
    const { ctx, page } = await open("/dev/carbon-board", "desktop", theme)
    try {
      if (theme === "dark") {
        await page.getByRole("button", { name: "dark" }).click()
        await page.waitForTimeout(1200)
      }
      const section = page.locator("section", { has: page.getByRole("heading", { name: "AI-native primitives and charts" }) }).first()
      await section.scrollIntoViewIfNeeded()
      await page.waitForTimeout(1200)
      await section.screenshot({ path: join(OUT, `board-ai-native-${theme}.png`) })
      results.push({ name: `board-ai-native-${theme}`, file: `board-ai-native-${theme}.png`, route: "/dev/carbon-board", viewport: "desktop", theme, class: "internal design board (placeholder content)" })
      console.log("ok board", theme)
    } catch (e) {
      console.log("FAIL board", theme, String(e).slice(0, 200))
    } finally {
      await ctx.close()
    }
  }
}

writeFileSync(join(OUT, "manifest.json"), JSON.stringify({ base: BASE, buildId: BUILD_ID, at: new Date().toISOString(), results }, null, 2))
await browser.close()
