/**
 * Capture + assert the voice UI: inline waveform and orb takeover, both speakers,
 * both breakpoints, light and dark.
 *
 * Assertions here deliberately target the VISIBLE painted element (bar widths,
 * orb diameter, computed colors), not wrappers — a size check on a wrapper passed
 * during the avatar pass while the actual mark inside had collapsed.
 *
 * Theme is driven through next-themes' localStorage key, NOT Playwright's
 * colorScheme: dark mode here is class-based, and next-themes rewrites
 * <html class> on mount, so any class we set ourselves is undone before paint.
 */
import { chromium } from "@playwright/test"
import { mkdir } from "node:fs/promises"

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000"
const OUT = "docs/delivery/shots/voice-ui"
const URL = `${BASE}/e2e/shots/voice-states`

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]
const THEMES = ["light", "dark"]

let failures = 0
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "  PASS" : "  FAIL"} ${label}${detail ? ` — ${detail}` : ""}`)
  if (!ok) failures++
}

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch()

for (const theme of THEMES) {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
    })
    const page = await context.newPage()
    await page.addInitScript((t) => localStorage.setItem("theme", t), theme)
    await page.goto(URL, { waitUntil: "networkidle" })
    await page.waitForTimeout(400)

    console.log(`\n[${theme} / ${vp.name}]`)

    // Filenames claim a theme; this proves it. Without this the four "dark"
    // captures in the avatar pass were silently light.
    const htmlClass = await page.evaluate(() => document.documentElement.className)
    check("theme class applied", htmlClass.split(/\s+/).includes(theme), `class="${htmlClass}"`)

    // ── Inline waveform ───────────────────────────────────────────────────────
    const userWave = page.locator('[data-shot="wave-user"] .gv-wave-bar')
    const agentWave = page.locator('[data-shot="wave-agent"] .gv-wave-bar')
    check("user waveform has 7 bars", (await userWave.count()) === 7)
    check("agent waveform has 7 bars", (await agentWave.count()) === 7)

    const barBox = await userWave.first().boundingBox()
    check("bar is 3px wide", barBox && Math.round(barBox.width) === 3, `${barBox?.width}px`)

    // Bars must NOT be uniform: a single shared keyframe would make them move in
    // lockstep, which reads as a ripple rather than speech.
    const heights = await userWave.evaluateAll((els) =>
      els.map((el) => Math.round(el.getBoundingClientRect().height)),
    )
    check("bar heights vary", new Set(heights).size > 1, `heights=[${heights.join(",")}]`)

    // Distinct per-speaker duration is the whole reason the two are told apart
    // without reading a label.
    const durations = await page.evaluate(() => {
      const pick = (sel) => {
        const el = document.querySelector(`${sel} .gv-wave-bar`)
        return el ? getComputedStyle(el).animationDuration : null
      }
      return { user: pick('[data-shot="wave-user"]'), agent: pick('[data-shot="wave-agent"]') }
    })
    check("user duration 0.6s", durations.user === "0.6s", String(durations.user))
    check("agent duration 1.1s", durations.agent === "1.1s", String(durations.agent))

    const waveColors = await page.evaluate(() => {
      const pick = (sel) => {
        const el = document.querySelector(`${sel} .gv-wave-bar`)
        return el ? getComputedStyle(el).backgroundColor : null
      }
      return { user: pick('[data-shot="wave-user"]'), agent: pick('[data-shot="wave-agent"]') }
    })
    // Compare as strings only: never parse a computed color numerically — Tailwind
    // v4 returns lab(), and an rgb-shaped regex misreads lightness as red.
    check(
      "speaker colors differ",
      waveColors.user !== waveColors.agent,
      `user=${waveColors.user} agent=${waveColors.agent}`,
    )

    await page.screenshot({ path: `${OUT}/wave-${theme}-${vp.name}.png`, fullPage: false })

    // ── Orb takeover, both speakers ───────────────────────────────────────────
    for (const speaker of ["user", "agent"]) {
      const label = speaker === "user" ? "you speaking" : "Gravitre speaking"
      await page.getByRole("button", { name: `Open orb — ${label}` }).click()
      await page.waitForSelector("[data-voice-orb]", { state: "visible" })
      await page.waitForTimeout(250)

      const circle = page.locator("[data-voice-orb-circle]")
      const box = await circle.boundingBox()
      // Pulse scales the orb, so the painted box legitimately exceeds the base
      // diameter; assert a band around the expected size rather than equality.
      const expected = vp.name === "mobile" ? 220 : 280
      check(
        `orb ~${expected}px (${speaker})`,
        box && box.width >= expected - 2 && box.width <= expected * 1.12,
        `${Math.round(box?.width ?? 0)}px`,
      )

      const anim = await circle.evaluate((el) => getComputedStyle(el).animationName)
      check(
        `orb uses ${speaker} pulse`,
        anim === (speaker === "user" ? "gv-orb-pulse-user" : "gv-orb-pulse-agent"),
        anim,
      )

      const text = await page.locator("[data-voice-orb]").innerText()
      const wantLabel = speaker === "user" ? "You're speaking" : "Gravitre is speaking"
      check(`orb label "${wantLabel}"`, text.includes(wantLabel))
      check("exit-to-text control present", text.includes("Tap to switch to text"))

      await page.screenshot({ path: `${OUT}/orb-${speaker}-${theme}-${vp.name}.png` })

      // Centre tap must collapse (stay in voice), never exit.
      await page
        .getByRole("button", { name: /Return to inline waveform/ })
        .click({ position: { x: 12, y: 12 } })
      await page.waitForTimeout(200)
      check(
        `centre tap collapses orb (${speaker})`,
        (await page.locator("[data-voice-orb]").count()) === 0,
      )
    }

    await context.close()
  }
}

// Reduced motion is an accessibility requirement, so assert the animation is
// actually gone rather than trusting the media query.
{
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    reducedMotion: "reduce",
  })
  const page = await context.newPage()
  await page.addInitScript(() => localStorage.setItem("theme", "light"))
  await page.goto(URL, { waitUntil: "networkidle" })
  await page.waitForTimeout(300)
  console.log("\n[reduced motion]")

  const state = await page.evaluate(() => {
    const bars = Array.from(document.querySelectorAll('[data-shot="wave-user"] .gv-wave-bar'))
    return {
      names: bars.map((b) => getComputedStyle(b).animationName),
      heights: bars.map((b) => Math.round(b.getBoundingClientRect().height)),
    }
  })
  check("waveform animation disabled", state.names.every((n) => n === "none"), state.names.join(","))
  // Frozen must still LOOK like a waveform, not seven identical stubs.
  check(
    "frozen bars keep distinct heights",
    new Set(state.heights).size > 1,
    `heights=[${state.heights.join(",")}]`,
  )
  await page.screenshot({ path: `${OUT}/wave-reduced-motion.png` })
  await context.close()
}

await browser.close()
console.log(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`)
process.exit(failures === 0 ? 0 : 1)
