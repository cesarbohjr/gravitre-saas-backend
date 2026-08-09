#!/usr/bin/env node
/**
 * Capture + assert the shared stateful assistant avatar.
 *
 * Runs in the PROJECT sandbox (not the browser sandbox), so it can reach the
 * local dev server on localhost.
 *
 *   node scripts/shoot-avatar-states.mjs
 *
 * Assertions target values only real rendering can produce:
 *   - the four states each render their distinguishing element
 *   - a named agent keeps its own icon/color WHILE animating (identity + state)
 *   - all three surfaces render the same avatar component (same box size)
 *   - reduced-motion collapses animation to a static mark
 */
import { chromium } from "@playwright/test"
import { mkdirSync } from "node:fs"

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000"
const URL = `${BASE}/e2e/shots/avatar-states`
const OUT = "/tmp/agent-browser"
mkdirSync(OUT, { recursive: true })

const failures = []
const notes = []
function check(label, ok, detail = "") {
  if (ok) notes.push(`PASS ${label}${detail ? ` — ${detail}` : ""}`)
  else failures.push(`${label}${detail ? ` — ${detail}` : ""}`)
}

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]

const browser = await chromium.launch()

for (const scheme of ["light", "dark"]) {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      colorScheme: scheme,
      deviceScaleFactor: 2,
    })
    const page = await context.newPage()
    const response = await page.goto(URL, { waitUntil: "networkidle" })

    // A 200 is not enough on its own: Next dev embeds the 404 template in every
    // page, so grepping HTML for "not found" is a false positive. Use status.
    check(`${scheme}/${vp.name} route status`, response?.status() === 200, `got ${response?.status()}`)

    await page.waitForSelector('[data-testid="avatar-states-root"]')

    // Let the keyframe loops reach a visible mid-phase before capture, otherwise
    // every animated state screenshots at its identical t=0 frame.
    await page.waitForTimeout(600)

    await page.screenshot({
      path: `${OUT}/avatar-${scheme}-${vp.name}.png`,
      fullPage: true,
    })

    if (vp.name === "desktop" && scheme === "dark") {
      // ── The four states must be visually distinct, not four copies ──────────
      const defaultStates = page.locator('[data-testid="states-default"] > div')
      check("four default states rendered", (await defaultStates.count()) === 4)

      // Speaking replaces the mark with three bars; idle must NOT have them.
      const speakingBars = page
        .locator('[data-testid="states-default"] > div')
        .nth(3)
        .locator("span > span")
      check("speaking renders 3 waveform bars", (await speakingBars.count()) === 3)

      const idleBars = page
        .locator('[data-testid="states-default"] > div')
        .nth(0)
        .locator("span > span")
      check("idle renders no waveform bars", (await idleBars.count()) === 0)

      // Thinking/searching are live regions; idle and speaking must not be.
      const thinkingRole = await page
        .locator('[data-testid="states-default"] > div')
        .nth(1)
        .locator("[role=status]")
        .count()
      check("thinking is an aria live region", thinkingRole === 1)

      const idleRole = await page
        .locator('[data-testid="states-default"] > div')
        .nth(0)
        .locator("[role=status]")
        .count()
      check("idle is not a live region", idleRole === 0)

      // ── Identity + state compose (the actual regression) ───────────────────
      // A named agent, while animating, must still show its OWN icon+gradient.
      // The purple gradient class is something only the real identity layer
      // produces, so its presence proves identity was not replaced by state.
      const namedThinking = page.locator('[data-testid="states-named"] > div').nth(1)
      const namedHtml = await namedThinking.innerHTML()
      check(
        "named agent keeps its own color while thinking",
        /purple/.test(namedHtml),
        "expected the agent's purple identity gradient inside the animating avatar",
      )
      check(
        "named agent renders an identity icon (not the Gravitre mark)",
        namedHtml.includes("<svg") && !namedHtml.includes("gravitre-mark"),
      )

      // Default assistant must use the Gravitre mark, not an agent icon.
      const defaultIdleHtml = await page
        .locator('[data-testid="states-default"] > div')
        .nth(0)
        .innerHTML()
      check("default assistant uses the Gravitre mark", defaultIdleHtml.includes("gravitre-mark"))

      // ── Part C: all three surfaces use the SAME component ─────────────────
      // Identical rendered box size across surfaces is the observable proof that
      // one component renders all three; a re-implementation would drift.
      const surfaceAvatars = page.locator('[data-testid="surface-comparison"] [role=status]')
      const surfaceCount = await surfaceAvatars.count()
      check("three surfaces each show a thinking avatar", surfaceCount === 3, `got ${surfaceCount}`)

      const boxes = []
      for (let i = 0; i < surfaceCount; i++) {
        const box = await surfaceAvatars.nth(i).boundingBox()
        boxes.push(box ? `${Math.round(box.width)}x${Math.round(box.height)}` : "none")
      }
      check(
        "all three surface avatars are the same size",
        new Set(boxes).size === 1,
        `sizes: ${boxes.join(", ")}`,
      )

      // ── Searching from a real in-flight tool call ──────────────────────────
      const searchingLive = await page
        .locator('[data-testid="searching-surface"] [role=status]')
        .count()
      check(
        "in-flight tool call drives the searching state",
        searchingLive >= 1,
        `found ${searchingLive} live-region avatar(s)`,
      )
    }

    await context.close()
  }
}

// ── prefers-reduced-motion must fall back to a static mark ──────────────────
{
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    reducedMotion: "reduce",
    deviceScaleFactor: 2,
  })
  const page = await context.newPage()
  await page.goto(URL, { waitUntil: "networkidle" })
  await page.waitForSelector('[data-testid="avatar-states-root"]')
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/avatar-reduced-motion.png`, fullPage: true })

  // The rotating searching arc and the pulsing halo are motion-only elements and
  // must not be in the tree at all under reduce.
  const html = await page.locator('[data-testid="avatar-state-matrix"]').innerHTML()
  check("reduced motion drops the conic searching arc", !html.includes("conic-gradient"))
  check("reduced motion still renders the mark", html.includes("gravitre-mark"))
  await context.close()
}

await browser.close()

console.log(notes.join("\n"))
if (failures.length) {
  console.error(`\nFAIL (${failures.length}):`)
  for (const f of failures) console.error(" -", f)
  process.exit(1)
}
console.log(`\nAll checks passed. Screenshots in ${OUT}/`)
