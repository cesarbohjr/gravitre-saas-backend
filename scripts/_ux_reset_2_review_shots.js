/**
 * One-off capture for UX Reset 2.0 review. Not a product runtime.
 */
const { chromium } = require("playwright")
const { mkdirSync } = require("node:fs")
const { join } = require("node:path")

const OUT = join(process.cwd(), "e2e", "artifacts", "ux-reset-2-review")
const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3001"

const shots = [
  ["nucleo-scale", "/dev/ai-workspace-preview?s=nucleo&scene=default", 1280, 800],
  ["ai-empty", "/dev/ai-workspace-preview?s=ai&scene=empty", 1280, 800],
  ["ai-loading", "/dev/ai-workspace-preview?s=ai&scene=loading", 1280, 800],
  ["ai-error", "/dev/ai-workspace-preview?s=ai&scene=error", 1280, 800],
  ["ai-compact-conversation", "/dev/ai-workspace-preview?s=ai&scene=compact-conversation", 1280, 800],
  ["ai-compact-voice-listen", "/dev/ai-workspace-preview?s=ai&scene=compact-voice-listen", 1280, 800],
  ["ai-compact-voice-speak", "/dev/ai-workspace-preview?s=ai&scene=compact-voice-speak", 1280, 800],
  ["ai-expanded-conversation", "/dev/ai-workspace-preview?s=ai&scene=expanded-conversation", 1440, 900],
  ["ai-expanded-history", "/dev/ai-workspace-preview?s=ai&scene=expanded-history", 1440, 900],
  ["ai-expanded-work", "/dev/ai-workspace-preview?s=ai&scene=expanded-work", 1440, 900],
  ["ai-expanded-tool", "/dev/ai-workspace-preview?s=ai&scene=expanded-tool", 1440, 900],
  ["ai-fullscreen-work", "/dev/ai-workspace-preview?s=ai&scene=fullscreen-work", 1728, 960],
  ["ai-fullscreen-inspect", "/dev/ai-workspace-preview?s=ai&scene=fullscreen-inspect", 1728, 960],
  ["ai-mobile-conversation", "/dev/ai-workspace-preview?s=ai&scene=mobile-conversation", 390, 844],
  ["ai-mobile-work", "/dev/ai-workspace-preview?s=ai&scene=mobile-work", 390, 844],
  ["ai-mobile-inspect", "/dev/ai-workspace-preview?s=ai&scene=mobile-inspect", 390, 844],
  ["agents-team", "/dev/ai-workspace-preview?s=agents&scene=default", 1440, 900],
  ["agents-selected", "/dev/ai-workspace-preview?s=agents&scene=selected", 1440, 900],
  ["agents-list", "/dev/ai-workspace-preview?s=agents&scene=list", 1440, 900],
  ["agents-graph", "/dev/ai-workspace-preview?s=agents&scene=graph", 1440, 900],
  ["agents-empty", "/dev/ai-workspace-preview?s=agents&scene=empty", 1440, 900],
  ["agents-mobile", "/dev/ai-workspace-preview?s=agents&scene=mobile", 390, 844],
  ["rel-default", "/dev/ai-workspace-preview?s=relationships&scene=default", 1440, 900],
  ["rel-selected", "/dev/ai-workspace-preview?s=relationships&scene=selected", 1440, 900],
  ["rel-empty", "/dev/ai-workspace-preview?s=relationships&scene=empty", 1440, 900],
  ["rel-loading", "/dev/ai-workspace-preview?s=relationships&scene=loading", 1440, 900],
  ["rel-error", "/dev/ai-workspace-preview?s=relationships&scene=error", 1440, 900],
  ["perf-default", "/dev/ai-workspace-preview?s=performance&scene=default", 1440, 900],
  ["perf-empty", "/dev/ai-workspace-preview?s=performance&scene=empty", 1440, 900],
  ["perf-loading", "/dev/ai-workspace-preview?s=performance&scene=loading", 1440, 900],
  ["perf-error", "/dev/ai-workspace-preview?s=performance&scene=error", 1440, 900],
  ["wf-default", "/dev/ai-workspace-preview?s=workflows&scene=default", 1440, 900],
  ["wf-selected", "/dev/ai-workspace-preview?s=workflows&scene=selected", 1440, 900],
  ["wf-empty", "/dev/ai-workspace-preview?s=workflows&scene=empty", 1440, 900],
  ["wf-error", "/dev/ai-workspace-preview?s=workflows&scene=error", 1440, 900],
  ["runs-outcome", "/dev/ai-workspace-preview?s=runs&scene=default", 1440, 900],
  ["runs-trace", "/dev/ai-workspace-preview?s=runs&scene=selected", 1440, 900],
  ["runs-empty", "/dev/ai-workspace-preview?s=runs&scene=empty", 1440, 900],
  ["runs-error", "/dev/ai-workspace-preview?s=runs&scene=error", 1440, 900],
  ["connectors-default", "/dev/ai-workspace-preview?s=connectors&scene=default", 1440, 900],
  ["connectors-selected", "/dev/ai-workspace-preview?s=connectors&scene=selected", 1440, 900],
  ["connectors-empty", "/dev/ai-workspace-preview?s=connectors&scene=empty", 1440, 900],
  ["connectors-error", "/dev/ai-workspace-preview?s=connectors&scene=error", 1440, 900],
]

async function main() {
  mkdirSync(OUT, { recursive: true })
  let browser
  try {
    browser = await chromium.launch({ channel: "chrome" })
  } catch {
    browser = await chromium.launch()
  }
  const page = await browser.newPage()
  for (const [name, path, width, height] of shots) {
    await page.setViewportSize({ width, height })
    const url = `${BASE}${path}`
    const res = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60_000 })
    if (!res || res.status() >= 400) {
      throw new Error(`${name} HTTP ${res && res.status()} ${url}`)
    }
    await page.locator("[data-review-surface]").waitFor({ timeout: 30_000 })
    await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true })
    console.log("wrote", name)
  }
  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
