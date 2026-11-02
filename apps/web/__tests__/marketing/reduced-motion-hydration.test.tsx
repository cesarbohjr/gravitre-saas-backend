import { readFileSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"
import { afterEach, describe, expect, it } from "vitest"
import { renderToString } from "react-dom/server"
import { useReducedMotion } from "@/lib/use-reduced-motion"

function Probe() {
  return <span>{useReducedMotion() ? "reduced" : "motion"}</span>
}

/**
 * Visitors with Reduce Motion turned on used to get a client first render that
 * differed from the server HTML (framer-motion's useReducedMotion reads the
 * media query immediately). React then either regenerated the page (#418) or
 * kept the server's `opacity:0` and left content invisible (About page).
 * The hydration render must match the server no matter what the OS says.
 */

const g = globalThis as unknown as { window?: unknown }

function stubReduceMotion() {
  g.window = {
    matchMedia: (query: string) => ({
      matches: query.includes("prefers-reduced-motion: reduce"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
    }),
  }
}

afterEach(() => {
  delete g.window
})

describe("marketing reduced motion hydration", () => {
  it("reports motion during the server/hydration render even when the device prefers reduced motion", () => {
    stubReduceMotion()
    expect(renderToString(<Probe />)).toBe("<span>motion</span>")
  })

  it("keeps marketing components off framer-motion's hydration-unsafe useReducedMotion", () => {
    const root = join(process.cwd(), "components", "marketing")
    const offenders: string[] = []
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name)
        if (statSync(path).isDirectory()) walk(path)
        else if (/\.(tsx?|jsx?)$/.test(name)) {
          const src = readFileSync(path, "utf8")
          const framerImport = src.match(/import\s*\{([^}]*)\}\s*from\s*["'](framer-motion|motion\/react)["']/g) ?? []
          if (framerImport.some((line) => /\buseReducedMotion\b/.test(line))) offenders.push(path)
        }
      }
    }
    walk(root)
    expect(offenders).toEqual([])
  })
})

describe("marketing ambient motion under Reduce Motion", () => {
  const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8")

  it("exempts .mk-ambient (logo orbit, Nodus hub rim) from the global reduce-motion kill switch", () => {
    const block = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce) {\n  *:not(.mk-ambient"))
    expect(block.startsWith("@media (prefers-reduced-motion: reduce)")).toBe(true)
    expect(css).toContain("[data-composition] :not(.mk-ambient, .mk-ambient *)")
  })

  it("lets each CTA orbit ring set its own speed, as in Nodus", () => {
    const cta = readFileSync(join(process.cwd(), "components", "marketing", "nodus", "cta.tsx"), "utf8")
    expect(cta).toContain('"mk-ambient relative mx-auto')
    expect(cta.match(/animationDuration: `\$\{duration\}s`/g)?.length).toBe(2)
  })
})
