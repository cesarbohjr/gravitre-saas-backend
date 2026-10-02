import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

function source(relative: string) {
  return readFileSync(resolve(webRoot, relative), "utf8")
}

describe("Marketplace 3.0 outcome-first catalog", () => {
  it("leads catalog cards with outcome and KPI impact instead of component counts", () => {
    const page = source("app/marketplace/assets/page.tsx")
    expect(page).toContain("MarketplaceOutcomeSummary")
    expect(page).not.toContain('<span className="text-muted-foreground">Adds </span>')
    expect(page).toContain('<span className="font-medium text-foreground">Includes:</span>')
  })

  it("makes business impact and install readiness first-class on asset detail", () => {
    const page = source("app/marketplace/assets/[slug]/page.tsx")
    expect(page).toContain("Business impact")
    expect(page).toContain("MarketplaceOutcomeSummary")
    expect(page).toContain("Install readiness")
    expect(page).toContain("Ready to install")
  })

  it("renders verification level, play count, and KPI impact in the shared summary", () => {
    const summary = source("components/marketplace/marketplace-outcome-summary.tsx")
    expect(summary).toContain("verificationLevel")
    expect(summary).toContain("playCount")
    expect(summary).toContain("kpiImpact")
    expect(summary).toContain("Outcome verified")
    expect(summary).toContain("Production verified")
  })
})
