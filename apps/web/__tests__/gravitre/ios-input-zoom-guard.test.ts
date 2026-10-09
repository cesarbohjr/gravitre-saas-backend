import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

/**
 * iOS Safari zooms the page in when a focused field's font is under 16px and
 * stays zoomed after the keyboard closes, so the chat sheet stops fitting an
 * iPhone screen. app/globals.css raises fields to 16px on iOS only; the root
 * viewport keeps pinch-zoom on for low-vision users rather than blocking zoom.
 */
const webRoot = resolve(__dirname, "../..")
const css = readFileSync(resolve(webRoot, "app/globals.css"), "utf8")
const layout = readFileSync(resolve(webRoot, "app/layout.tsx"), "utf8")

describe("iOS focus zoom guard", () => {
  const block = css.match(/@supports \(-webkit-touch-callout: none\) \{([\s\S]*?)\n\}/)?.[1] ?? ""

  it("raises text fields to 16px on iOS only", () => {
    expect(block).toMatch(/textarea/)
    expect(block).toMatch(/input:not\(/)
    expect(block).toMatch(/font-size:\s*16px\s*!important/)
  })

  it("is not inside a cascade layer, so text-sm utilities cannot override it", () => {
    const before = css.slice(0, css.indexOf("@supports (-webkit-touch-callout: none)"))
    const opened = (before.match(/@layer [\w-]+\s*\{/g) ?? []).length
    expect(opened).toBe(0)
  })

  it("keeps pinch-zoom available", () => {
    expect(layout).toMatch(/userScalable:\s*true/)
    expect(layout).not.toMatch(/maximumScale:\s*1\b/)
  })
})
