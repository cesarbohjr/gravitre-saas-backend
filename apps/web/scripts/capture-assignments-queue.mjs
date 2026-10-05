// Capture the Assignments queue harness (/e2e/shots/assignments) at the phone
// viewport. Fixture data only; not owner-live evidence.
// Usage: node scripts/capture-assignments-queue.mjs <outDir> [base]
import { mkdirSync } from "node:fs"
import { join } from "node:path"
import { chromium } from "@playwright/test"

const OUT = process.argv[2] ?? "/tmp/agent-browser"
const BASE = process.argv[3] ?? "http://localhost:3000"
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({ headless: true })
for (const [name, width, height, theme] of [
  ["queue-mobile-dark", 390, 844, "dark"],
  ["queue-mobile-dark-full", 390, 2000, "dark"],
  ["queue-desktop-light", 1440, 1000, "light"],
]) {
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: theme, deviceScaleFactor: 2 })
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem("gravitre-app-theme", t)
      localStorage.setItem("gravitre-welcome-dismissed", "true")
    } catch {}
  }, theme)
  const page = await ctx.newPage()
  const errors = []
  page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 160)))
  await page.goto(`${BASE}/e2e/shots/assignments`, { waitUntil: "domcontentloaded", timeout: 120000 })
  await page.waitForSelector("[data-assignments-queue]", { timeout: 60000 }).catch(() => {})
  await page.waitForTimeout(2500)
  const metrics = await page.evaluate(() => {
    const queue = document.querySelector("[data-assignments-queue]")
    const small = [...(queue?.querySelectorAll("a,button") ?? [])]
      .map((el) => ({ text: el.textContent?.trim().slice(0, 30), h: Math.round(el.getBoundingClientRect().height) }))
      .filter((t) => t.h > 0 && t.h < 44)
    return {
      url: location.href,
      briefing: document.querySelector("[data-queue-briefing]")?.textContent ?? null,
      sections: [...document.querySelectorAll("[data-assignment-phase]")].map((s) => s.getAttribute("data-assignment-phase")),
      smallTargets: small,
      overflowX: document.documentElement.scrollWidth > window.innerWidth,
    }
  })
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: false })
  console.log(name, JSON.stringify(metrics), errors.length ? `errors=${JSON.stringify(errors.slice(0, 3))}` : "")
  await ctx.close()
}
await browser.close()
