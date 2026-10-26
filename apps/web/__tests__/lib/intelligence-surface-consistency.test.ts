import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const pages = [
  "app/(app)/intelligence/learning/page.tsx",
  "app/(app)/intelligence/performance/page.tsx",
  "app/(app)/intelligence/predictive/page.tsx",
  "app/(app)/intelligence/reports/page.tsx",
  "app/(app)/models/page.tsx",
]

describe("Intelligence 3.0 surface consistency", () => {
  it("uses the shared Intelligence page frame instead of per-route width caps", () => {
    for (const page of pages) {
      const source = readFileSync(resolve(webRoot, page), "utf8")
      // The v3 design's 1320px column and gutters come from one token, so every page lines up.
      expect(source).toContain("className={INTELLIGENCE_PAGE_FRAME}")
      expect(source).not.toContain("max-w-6xl")
      expect(source).not.toContain("mx-auto max-w")
    }
  })

  it("keeps the frame on the shared page gutters", () => {
    const tokens = readFileSync(resolve(webRoot, "lib/design-system.ts"), "utf8")
    expect(tokens).toMatch(/INTELLIGENCE_PAGE_FRAME = `\$\{PAGE_FRAME\} mx-auto w-full max-w-\[1320px\]/)
  })
})
