import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const pages = [
  "app/intelligence/learning/page.tsx",
  "app/intelligence/performance/page.tsx",
  "app/intelligence/predictive/page.tsx",
  "app/intelligence/reports/page.tsx",
  "app/models/page.tsx",
]

describe("Intelligence 3.0 surface consistency", () => {
  it("uses the canonical authenticated page gutters without legacy route width caps", () => {
    for (const page of pages) {
      const source = readFileSync(resolve(webRoot, page), "utf8")
      // Reports and Impact (v2) use the shared PAGE_FRAME token, which carries the same gutters.
      const usesPageFrame =
        (page === "app/intelligence/reports/page.tsx" ||
          page === "app/intelligence/performance/page.tsx" ||
          page === "app/intelligence/predictive/page.tsx" ||
          page === "app/models/page.tsx") &&
        source.includes("className={PAGE_FRAME}")
      if (!usesPageFrame) {
        expect(source).toContain("px-[var(--np-page-pad-sm)]")
        expect(source).toContain("sm:px-[var(--np-page-pad)]")
      }
      expect(source).not.toContain("max-w-6xl")
      expect(source).not.toContain("mx-auto max-w")
    }
  })
})
