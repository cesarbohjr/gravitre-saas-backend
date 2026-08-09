import { chromium } from "@playwright/test"
const b = await chromium.launch()
const p = await b.newPage()
const errs = []
p.on("console", (m) => {
  if (m.type() === "error") errs.push(m.text())
})
p.on("pageerror", (e) => errs.push("PAGEERROR: " + e.message))
await p.goto("http://localhost:3000/e2e/shots/avatar-states", { waitUntil: "networkidle" })
await p.waitForTimeout(1200)
console.log(errs.slice(0, 8).join("\n---\n") || "no console errors")
await b.close()
