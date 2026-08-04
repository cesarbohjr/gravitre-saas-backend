// Captures the chat-progress harness states for visual review.
// Requires a dev server started with PLAYWRIGHT_E2E=1.
// Usage: node scripts/capture-chat-progress-harness.mjs [baseUrl]
import { chromium } from "@playwright/test"

const TARGET = `${process.argv[2] ?? "http://127.0.0.1:3000"}/e2e/chat-progress`
const OUT = `/tmp/agent-browser/chat-progress-${Date.now()}.png`

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
const response = await page.goto(TARGET, { waitUntil: "networkidle" })
console.log("[v0] status", response?.status())

await page.waitForSelector('[data-testid="chat-progress-harness"]')
const text = await page.evaluate(() => document.body.innerText)

const rawPrefixes = (text.match(/(?:^|\n)\s*(?:Running|Completed):/g) ?? []).length
console.log("[v0] raw step prefixes rendered as labels:", rawPrefixes)
console.log("[v0] 'Create contact list' present:", text.includes("Create contact list"))
console.log("[v0] 'apollo-contacts-q1.csv' present:", text.includes("apollo-contacts-q1.csv"))

await page.screenshot({ path: OUT, fullPage: true })
console.log("[v0] screenshot:", OUT)
await browser.close()
