import { chromium } from "@playwright/test"

const b = await chromium.launch()
const p = await (
  await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" })
).newPage()

p.on("console", (m) => {
  const t = m.text()
  if (!/webpack-hmr|insights|Download the React/.test(t)) console.log(`[${m.type()}]`, t.slice(0, 180))
})
p.on("pageerror", (e) => console.log("PAGEERROR:", e.message.slice(0, 300)))

await p.goto("http://127.0.0.1:3000/e2e/shots/activity", { waitUntil: "domcontentloaded" })
await p.waitForTimeout(9000)

console.log("--- body ---")
console.log((await p.locator("body").innerText()).slice(0, 400))
console.log("listbox:", await p.locator('[role="listbox"]').count())

await b.close()
