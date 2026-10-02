import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

function source(relative: string) {
  return readFileSync(resolve(webRoot, relative), "utf8")
}

describe("Marketplace 3.0 outcome-first UX", () => {
  it("surfaces measurable Play count and certification in catalog rows", () => {
    const page = source("app/marketplace/assets/page.tsx")
    expect(page).toContain("outcomePackSummary")
    expect(page).toContain("measurable Plays")
    expect(page).toContain("Production verified")
    expect(page).toContain("Outcome:")
  })

  it("shows the Outcome Pack contract with Plays, KPIs, and source-of-record verification", () => {
    const detail = source("app/marketplace/assets/[slug]/page.tsx")
    expect(detail).toContain("Marketplace 3.0 operating capability")
    expect(detail).toContain("Measurable outcome contract")
    expect(detail).toContain("Included Plays")
    expect(detail).toContain("Measured KPIs")
    expect(detail).toContain("Source of record")
    expect(detail).toContain("Provider acceptance is not completion")
  })
})
