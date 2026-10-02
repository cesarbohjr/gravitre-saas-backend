import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

function source(relative: string) {
  return readFileSync(resolve(webRoot, relative), "utf8")
}

describe("Marketplace 3.0 authoritative certification read model", () => {
  it("does not infer Outcome Pack certification from legacy verified marketing flags", () => {
    const catalog = source("app/marketplace/assets/page.tsx")
    const detail = source("app/marketplace/assets/[slug]/page.tsx")

    expect(catalog).toContain('return "Compatible"')
    expect(detail).toContain('return "Compatible"')
    expect(catalog).not.toContain('return asset.verified ? "Verified" : "Compatible"')
    expect(detail).not.toContain('return asset.verified ? "Verified" : "Compatible"')
  })

  it("renders backend-derived Outcome Pack contract fields", () => {
    const catalog = source("app/marketplace/assets/page.tsx")
    const detail = source("app/marketplace/assets/[slug]/page.tsx")

    for (const field of ["certificationLevel", "playCount", "kpiKeys", "outcomeEvents", "runtimeProviders"]) {
      expect(catalog).toContain(field)
    }
    for (const field of ["certificationLevel", "playCount", "kpiKeys", "outcomeEvents", "runtimeProviders"]) {
      expect(detail).toContain(field)
    }
  })

  it("suppresses legacy Verified trust badges for Outcome Packs", () => {
    const catalog = source("app/marketplace/assets/page.tsx")
    const detail = source("app/marketplace/assets/[slug]/page.tsx")

    expect(catalog).toContain('asset.assetType === "outcome_pack" ? { ...asset, verified: false } : asset')
    expect(detail).toContain('asset.assetType === "outcome_pack" ? { ...asset, verified: false } : asset')
  })
})
