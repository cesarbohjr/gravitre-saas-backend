/**
 * Captures the home dashboard for the marketing hero (`public/nodus/dashboard@3x.png`).
 *
 * Uses the fixture harness at /e2e/shots/home so the capture is deterministic
 * and never points a camera at a live customer tenant.
 *
 *   node scripts/capture-dashboard-hero.mjs [--probe]
 */
import { chromium } from "@playwright/test"
import { mkdir } from "node:fs/promises"
import { join } from "node:path"

const BASE = process.env.SHOT_BASE_URL ?? "http://localhost:3000"
const OUT_DIR = join(process.cwd(), "apps/web/public/nodus")
const VIEWPORT = { width: 1440, height: 810 }
/** 1440 × 2.3 ≈ 3312 — matches legacy @3x marketing asset width. */
const SCALE = 2.3

const HIDE_DEV_OVERLAY = `
  nextjs-portal,
  [data-nextjs-toast],
  [data-nextjs-dev-tools-button] { display: none !important; }
`

async function probe(page) {
  const res = await page.goto(`${BASE}/e2e/shots/home`, { waitUntil: "domcontentloaded" })
  const host = new URL(page.url()).host
  const expected = new URL(BASE).host
  const ok = res?.status() === 200 && host === expected
  console.log(`probe: status=${res?.status()} host=${host} expected=${expected} ok=${ok}`)
  return ok
}

const browser = await chromium.launch()
try {
  const page = await browser.newPage({
    viewport: VIEWPORT,
    deviceScaleFactor: SCALE,
  })

  await page.addInitScript(() => {
    localStorage.setItem(
      "gravitre:selectedOrg",
      JSON.stringify({ id: "00000000-0000-0000-0000-000000000001", name: "Northwind Logistics" }),
    )
    localStorage.setItem("gravitre-welcome-dismissed", "true")
  })

  if (!(await probe(page))) process.exit(1)
  if (process.argv.includes("--probe")) process.exit(0)

  await page.goto(`${BASE}/e2e/shots/home`, { waitUntil: "networkidle" })
  await page.reload({ waitUntil: "networkidle" })
  await page.getByText("96.8%", { exact: false }).first().waitFor({ timeout: 20_000 })
  await page.getByText("GPT-4o", { exact: false }).first().waitFor({ timeout: 20_000 })
  await page.waitForTimeout(800)
  await page.addStyleTag({ content: HIDE_DEV_OVERLAY }).catch(() => {})

  await mkdir(OUT_DIR, { recursive: true })
  const out3x = join(OUT_DIR, "dashboard@3x.png")
  await page.screenshot({ path: out3x })
  console.log(`ok   ${out3x}`)
  await page.screenshot({ path: join(OUT_DIR, "dashboard.png") })
  console.log(`ok   ${join(OUT_DIR, "dashboard.png")}`)
} finally {
  await browser.close()
}
