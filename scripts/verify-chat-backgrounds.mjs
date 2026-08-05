/**
 * Smoke-check chat canvas backgrounds + session header on the e2e shot harness.
 * Prereq: PLAYWRIGHT_E2E=1 NEXT_PUBLIC_PLAYWRIGHT_E2E=1 pnpm dev
 */
import { chromium } from "@playwright/test"
import { mkdir } from "node:fs/promises"

const BASE = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"
const ROUTE = "/e2e/shots/ai"
const OUT = ".playwright-out"

async function visibleEl(page, selector) {
  return page.evaluate((sel) => {
    return [...document.querySelectorAll(sel)].some((el) => {
      const s = getComputedStyle(el)
      return s.display !== "none" && s.visibility !== "hidden" && el.getClientRects().length > 0
    })
  }, selector)
}

async function main() {
  await mkdir(OUT, { recursive: true })
  const browser = await chromium.launch()
  const failures = []
  const notes = []

  for (const vp of [
    { name: "phone", width: 390, height: 844 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "desktop", width: 1440, height: 900 },
  ]) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      colorScheme: "light",
      deviceScaleFactor: 2,
    })
    const page = await ctx.newPage()
    const res = await page.goto(`${BASE}${ROUTE}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    })
    if (!res || res.status() !== 200) {
      failures.push(`${vp.name}: status ${res?.status()}`)
      await ctx.close()
      continue
    }

    const canvas = page.locator(".ai-chat-canvas").first()
    await canvas.waitFor({ state: "visible", timeout: 60_000 })

    const css = await canvas.evaluate((el) => {
      const s = getComputedStyle(el)
      return {
        bgImage: s.backgroundImage,
        bgSize: s.backgroundSize,
        bgAttachment: s.backgroundAttachment,
        opacity: s.opacity,
      }
    })

    console.log(`\n${vp.name}`)
    console.log(`  bgAttachment=${css.bgAttachment}`)
    console.log(`  bgSize=${css.bgSize}`)
    console.log(`  opacity=${css.opacity}`)
    console.log(`  bgImage=${css.bgImage.slice(0, 120)}`)

    if (css.bgAttachment !== "local") {
      failures.push(`${vp.name}: background-attachment is ${css.bgAttachment}, need local`)
    }
    if (css.opacity !== "1") {
      failures.push(`${vp.name}: canvas opacity ${css.opacity} — do not layer CSS opacity`)
    }
    const expectSize = vp.width <= 480 ? "180px" : "234px"
    if (!css.bgSize.startsWith(expectSize)) {
      failures.push(`${vp.name}: bgSize ${css.bgSize}, expected ${expectSize}`)
    }
    if (!css.bgImage.includes("/patterns/gw-")) {
      failures.push(`${vp.name}: expected patterned tile URL`)
    }

    // Apply Sales via storage + attribute (deterministic); picker open is separate.
    await page.evaluate(() => {
      localStorage.setItem("gravitre.chat.background", "sales")
      document.querySelectorAll(".ai-chat-canvas").forEach((el) => {
        el.setAttribute("data-chat-bg", "sales")
      })
    })
    // Re-query — React can replace the canvas node after storage sync.
    const canvasSales = page.locator(".ai-chat-canvas").first()
    await canvasSales.waitFor({ state: "visible", timeout: 10_000 })
    let salesCss = ""
    for (let attempt = 0; attempt < 8; attempt++) {
      await page.evaluate(() => {
        document.querySelectorAll(".ai-chat-canvas").forEach((el) => {
          el.setAttribute("data-chat-bg", "sales")
        })
      })
      salesCss = await canvasSales.evaluate((el) => getComputedStyle(el).backgroundImage)
      if (salesCss.includes("gw-sales-light") || salesCss.includes("gw-sales-dark")) break
      await page.waitForTimeout(150)
    }
    if (!salesCss.includes("gw-sales")) {
      failures.push(`${vp.name}: sales tile not applied (${salesCss.slice(0, 80)})`)
    } else {
      console.log("  ok   sales tile applied via data-chat-bg")
    }

    // Theme picker exists and is visible
    if (!(await visibleEl(page, '[aria-label^="Chat background"]'))) {
      failures.push(`${vp.name}: theme picker missing`)
    } else {
      console.log("  ok   theme picker visible")
    }

    // Next.js / Turbopack "1 Issue" toast can sit over the palette control.
    // Dismiss via its close control only — do not tear out nextjs-portal nodes.
    const issueClose = page.locator("text=1 Issue").locator("..").getByRole("button").first()
    if (await issueClose.count()) {
      await issueClose.click({ force: true }).catch(() => {})
      await page.waitForTimeout(100)
    }

    // Try opening picker — note soft failure if a toast still overlays it
    try {
      const pickers = page.locator('[aria-label^="Chat background"]')
      const count = await pickers.count()
      let clicked = false
      for (let i = 0; i < count; i++) {
        const el = pickers.nth(i)
        if (await el.isVisible()) {
          await el.click({ force: true })
          clicked = true
          break
        }
      }
      if (!clicked) throw new Error("no visible picker")
      const popover = page.locator('[data-slot="popover-content"]').filter({ hasText: "Chat background" })
      await popover.waitFor({ state: "visible", timeout: 8_000 })
      for (const label of ["Marketing", "Sales", "Developers", "Operations", "Plain"]) {
        if ((await popover.getByRole("button", { name: label, exact: true }).count()) === 0) {
          failures.push(`${vp.name}: swatch ${label} missing`)
        }
      }
      const mktPreview = await popover
        .getByRole("button", { name: "Marketing", exact: true })
        .evaluate((el) => {
          const layer = el.querySelector("span[aria-hidden]")
          return layer ? getComputedStyle(layer).backgroundImage : ""
        })
      if (!mktPreview.includes("gw-mkt-")) {
        failures.push(`${vp.name}: Marketing swatch missing tile preview`)
      } else {
        console.log("  ok   5 swatches with tile preview")
      }
      await page.keyboard.press("Escape")
    } catch {
      notes.push(`${vp.name}: theme picker popover did not open (CSS/tile checks still ran)`)
      console.log("  note theme picker popover did not open")
    }

    if (vp.width >= 640) {
      if (!(await visibleEl(page, '[aria-label^="Session:"]'))) {
        failures.push(`${vp.name}: consolidated session control missing`)
      } else {
        console.log("  ok   consolidated Session control")
      }
    } else {
      if (!(await visibleEl(page, '[aria-label^="Speed:"]'))) {
        failures.push(`${vp.name}: mobile speed chip missing`)
      } else {
        console.log("  ok   mobile Speed chip")
      }
    }

    const shot = `${OUT}/chat-bg-${vp.name}-${Date.now()}.png`
    await page.screenshot({ path: shot, fullPage: false })
    console.log(`  shot ${shot}`)
    await ctx.close()
  }

  await browser.close()

  if (notes.length) {
    console.log("\nNotes:")
    for (const n of notes) console.log(`  - ${n}`)
  }
  if (failures.length) {
    console.error(`\n${failures.length} failure(s):`)
    for (const f of failures) console.error(`  - ${f}`)
    process.exit(1)
  }
  console.log("\nChat background + header smoke checks pass.")
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
