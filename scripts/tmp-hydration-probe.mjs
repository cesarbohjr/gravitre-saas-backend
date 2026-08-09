import { chromium } from "@playwright/test"

const browser = await chromium.launch()
const page = await browser.newPage()
const errors = []
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text().slice(0, 200))
})
page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message.slice(0, 200)))

await page.goto("http://localhost:3000/e2e/shots/avatar-states", { waitUntil: "networkidle" })
await page.waitForTimeout(1500)

const hydration = errors.filter((e) => /hydrat|did not match|server rendered/i.test(e))
console.log("total console errors:", errors.length)
console.log("hydration errors:", hydration.length)
if (hydration.length) console.log(hydration.join("\n---\n"))
else if (errors.length) console.log("non-hydration errors:\n" + errors.slice(0, 3).join("\n---\n"))
else console.log("clean")

await browser.close()
