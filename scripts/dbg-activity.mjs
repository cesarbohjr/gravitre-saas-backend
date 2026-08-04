import { chromium } from "@playwright/test"

const b = await chromium.launch()
const p = await (
  await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" })
).newPage()
p.on("pageerror", (e) => console.log("PAGEERROR:", e.message))
p.on("console", (m) => {
  if (m.type() === "error" && !m.text().includes("webpack-hmr")) console.log("CONSOLE:", m.text())
})
for (const route of ["activity", "agents"]) {
  await p.goto(`http://127.0.0.1:3000/e2e/shots/${route}`, { waitUntil: "networkidle" })
  await p.waitForTimeout(4000)
  console.log(`\n=== ${route} ===`)
  console.log("URL:", p.url())
  console.log("listbox:", await p.locator('[role="listbox"]').count())
  console.log("TEXT:", (await p.locator("body").innerText()).slice(0, 600))
  await p.screenshot({ path: `/tmp/agent-browser/dbg-${route}.png` })
}
await b.close()
