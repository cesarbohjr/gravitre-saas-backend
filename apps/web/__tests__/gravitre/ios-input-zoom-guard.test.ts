import { readFileSync, readdirSync, statSync } from "node:fs"
import { join, relative, resolve } from "node:path"
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
const IOS = "@supports (-webkit-touch-callout: none)"

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return cssFiles(path)
    return name.endsWith(".css") ? [path] : []
  })
}

describe("iOS focus zoom guard", () => {
  const block = css.slice(css.indexOf(IOS), css.indexOf("\n}\n", css.indexOf(IOS)))

  it("raises text fields to 16px on iOS only", () => {
    expect(block).toMatch(/:where\(/)
    expect(block).toMatch(/textarea/)
    expect(block).toMatch(/input:not\(/)
    expect(block).toMatch(/font-size:\s*16px;/)
  })

  it("sits outside cascade layers so text-sm utilities cannot override it", () => {
    const before = css.slice(0, css.indexOf(IOS))
    expect(before.match(/@layer [\w-]+\s*\{/g) ?? []).toHaveLength(0)
  })

  it("does not shrink fields that are deliberately larger than 16px", () => {
    expect(block).not.toMatch(/!important/)
  })

  it("gives every redesign field styled under 16px (or inheriting) its own iOS override", () => {
    const missing: string[] = []
    for (const file of cssFiles(resolve(webRoot, "components"))) {
      const text = readFileSync(file, "utf8")
      for (const match of text.matchAll(/^([^{}@\n][^{}\n]*)\{([^}]*)\}/gm)) {
        const selector = match[1].trim()
        // `font: inherit` takes the parent's (usually 14px) size, so it counts too.
        const size = match[2].match(/font-size:\s*([\d.]+)px/)
        const inherits = /(^|;)\s*font:/.test(match[2])
        if (size ? Number(size[1]) >= 16 : !inherits) continue
        if (!/\b(input|textarea|select)\b/.test(selector)) continue
        const override = text.indexOf(IOS, match.index)
        if (override === -1 || !text.slice(override, override + 400).includes(selector)) {
          missing.push(`${relative(webRoot, file)}: ${selector}`)
        }
      }
    }
    expect(missing).toEqual([])
  })

  it("keeps pinch-zoom available", () => {
    expect(layout).toMatch(/userScalable:\s*true/)
    expect(layout).not.toMatch(/maximumScale:\s*1\b/)
  })
})
