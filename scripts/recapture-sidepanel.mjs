// Throwaway: re-capture the side panel shot at a realistic panel height.
// The first capture used a very tall viewport; SidePanelApp is `min-h-dvh`, so
// the panel stretched to ~1500px while its content only filled ~700px, leaving
// most of the image blank. Deleted after use.
import { chromium } from "@playwright/test"

const OUT = "apps/web/public/product/extension-sidepanel.png"
const TARGET = "http://localhost:3000/e2e/ext-harness/preview.html?shot=sidepanel"

const browser = await chromium.launch()
const page = await browser.newPage({
  // The panel's own content is only ~400px tall and its footer is pinned to the
  // bottom of `min-h-dvh`, so a tall viewport just inserts dead space between
  // the two. Size the viewport to the content instead.
  viewport: { width: 400, height: 480 },
  deviceScaleFactor: 2,
})

const res = await page.goto(TARGET, { waitUntil: "networkidle" })
console.log("[v0] status", res?.status(), "host", new URL(page.url()).host)

// Assert we captured the real surface and not a redirect/404 shell.
const text = await page.locator("body").innerText()
for (const needle of ["Enrich this page", "Connected", "ACTIVE CONNECTORS"]) {
  if (!text.includes(needle)) {
    throw new Error(`missing "${needle}" -- got: ${text.slice(0, 300)}`)
  }
}

const box = await page.locator("#root > div").boundingBox()
console.log("[v0] surface box", box)

await page.screenshot({ path: OUT, fullPage: true })
await browser.close()
console.log("[v0] wrote", OUT)
