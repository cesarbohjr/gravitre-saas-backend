import { chromium } from "@playwright/test"

const URL = "http://localhost:3000/e2e/shots/voice-states"
const browser = await chromium.launch()
const page = await browser.newPage({ reducedMotion: "reduce" })
await page.goto(URL, { waitUntil: "networkidle" })
await page.waitForSelector(".gv-wave-bar")

const out = await page.evaluate(() => {
  const matches = window.matchMedia("(prefers-reduced-motion: reduce)").matches
  const bar = document.querySelector(".gv-wave-bar")
  const cs = getComputedStyle(bar)

  // Find every rule in the CSSOM that mentions gv-wave-bar, with its media text.
  const found = []
  for (const sheet of Array.from(document.styleSheets)) {
    let rules
    try {
      rules = sheet.cssRules
    } catch {
      continue
    }
    const walk = (list, media, layer) => {
      for (const r of Array.from(list)) {
        if (r.cssRules) {
          walk(
            r.cssRules,
            r.media?.mediaText ?? media,
            r.name !== undefined ? `@layer ${r.name}` : layer,
          )
        } else if (r.selectorText?.includes("gv-wave-bar")) {
          found.push({
            sel: r.selectorText,
            media: media || "-",
            layer: layer || "-",
            anim: r.style.animation || r.style.animationName || "-",
          })
        }
      }
    }
    walk(rules, "", "")
  }
  return { matches, animationName: cs.animationName, found }
})

console.log("prefers-reduced-motion matches:", out.matches)
console.log("computed animation-name:", out.animationName)
console.log("\nCSSOM rules mentioning gv-wave-bar:")
for (const r of out.found) console.log(`  [${r.layer}] [${r.media}] ${r.sel} -> ${r.anim}`)

await browser.close()
