#!/usr/bin/env node
import { chromium } from "@playwright/test"
import { fileURLToPath } from "node:url"
import path from "node:path"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const htmlPath = path.join(__dirname, "assets/ai-transparency-approval-hero.html")
const outputPath = path.join(
  __dirname,
  "../apps/web/public/images/blog/ai-transparency-governance-hero.jpg"
)

const browser = await chromium.launch()
const page = await browser.newPage({
  viewport: { width: 1200, height: 675 },
  deviceScaleFactor: 2,
})
await page.goto(`file://${htmlPath}`)
await page.screenshot({
  path: outputPath,
  type: "jpeg",
  quality: 92,
  clip: { x: 0, y: 0, width: 1200, height: 675 },
})
await browser.close()
console.log(`Wrote ${outputPath}`)
