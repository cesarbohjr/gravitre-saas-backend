// WCAG 2.1 A/AA scan of harness routes on a local production build (fixture data,
// no sign-in; not owner-live evidence).
// Usage: AXE_SOURCE=<path to axe.min.js> node scripts/axe-harness-scan.mjs <outFile> [base]
import { readFileSync, writeFileSync } from "node:fs"
import { chromium } from "@playwright/test"

const OUT = process.argv[2]
const BASE = process.argv[3] || "http://127.0.0.1:3010"
const axeSource = readFileSync(process.env.AXE_SOURCE, "utf8")
const ROUTES = [
  "/e2e/shots/home",
  "/e2e/shots/agent-detail",
  "/e2e/shots/connectors",
  "/e2e/shots/agents",
  "/e2e/shots/builder",
  "/dev/carbon-board",
]

const browser = await chromium.launch({
  executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
})
const results = []
for (const scheme of ["light", "dark"]) {
  for (const route of ROUTES) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme })
    await ctx.addInitScript((t) => {
      try {
        localStorage.setItem("gravitre-app-theme", t)
        localStorage.setItem("gravitre-welcome-dismissed", "true")
      } catch {}
    }, scheme)
    const page = await ctx.newPage()
    await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 180000 })
    await page.waitForTimeout(6000)
    await page.addScriptTag({ content: axeSource })
    const violations = await page.evaluate(async () => {
      const out = await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } })
      return out.violations.map((v) => ({ id: v.id, impact: v.impact, count: v.nodes.length, targets: v.nodes.slice(0, 4).map((n) => n.target.join(" ")) }))
    })
    const theme = await page.evaluate(() => document.documentElement.className)
    results.push({ scheme, route, theme, violations })
    console.log(scheme, route, violations.map((v) => `${v.id}:${v.impact}:${v.count}`).join(", ") || "none")
    await ctx.close()
  }
}
writeFileSync(OUT, JSON.stringify({ base: BASE, at: new Date().toISOString(), results }, null, 2))
await browser.close()
