import { existsSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { ILLUSTRATIONS } from "@/components/gravitre/illustration"
import {
  MARKET_ART_FALLBACK,
  MARKET_ART_NAMES,
  marketArtFor,
  resolveMarketArt,
  resolveMarketArtName,
} from "@/lib/marketplace-category-art"

describe("marketplace category art", () => {
  it("covers exactly the 15 market illustrations, each registered and on disk", () => {
    expect(MARKET_ART_NAMES).toHaveLength(15)
    for (const name of MARKET_ART_NAMES) {
      expect(name.startsWith("market-")).toBe(true)
      expect(name in ILLUSTRATIONS).toBe(true)
      expect(existsSync(resolve(__dirname, `../../public/illustrations/${name}.svg`))).toBe(true)
      const art = marketArtFor(name)
      expect(art.src).toBe(`/illustrations/${name}.svg`)
      expect(art.alt.length).toBeGreaterThan(10)
    }
  })

  it.each([
    ["HubSpot Lead Qualification", "Sales", ["workflow", "starter", "sales"], "market-leads"],
    ["MSP Prospects Clay Enrichment → HubSpot Sync", "Sales", ["workflow"], "market-prospecting"],
    ["Salesforce Pipeline Review", "Sales", ["workflow"], "market-pipeline"],
    ["Deal Desk Approval Flow", "Revenue Operations", ["workflow", "revops"], "market-deals"],
    ["Zendesk Ticket Triage", "Support", ["workflow", "support"], "market-tickets"],
    ["SLA Breach Escalation", "Operations", ["workflow", "msp"], "market-tickets"],
    ["Customer Health Monitoring", "Customer Success", ["customer-success"], "market-support"],
    ["Marketing Campaign Production", "Marketing", ["marketing"], "market-campaigns"],
    ["SEO Analyst", "Marketing", ["marketing", "agent"], "market-site-health"],
    ["Invoice Exception Review", "Finance", ["finance"], "market-finance"],
    ["Weekly Team Status Report", "Revenue Operations", ["workflow", "revenue-operations"], "market-revenue"],
    ["Security Access Review", "Security", ["security"], "market-security"],
    ["New Hire Onboarding Checklist", "HR", ["hr"], "market-onboarding"],
    ["Customer onboarding kickoff", "Customer Success", [], "market-new-customers"],
    ["Product Feedback Synthesis", "Product", ["product"], "market-product"],
    ["GDPR policy review", null, [], "market-compliance"],
  ] as const)("maps %s to %s", (title, department, tags, expected) => {
    expect(resolveMarketArtName({ title, department, tags })).toBe(expected)
  })

  it("matches whole words only, so 'leader' or 'website' do not mis-route", () => {
    expect(resolveMarketArtName({ title: "Team leader digest", department: "Finance" })).toBe("market-finance")
    expect(resolveMarketArtName({ title: "Ad hoc digest", department: "Sales" })).toBe("market-pipeline")
  })

  it("falls back to the department, then the asset type, then the default", () => {
    expect(resolveMarketArtName({ title: "Starter pack", department: "Sales" })).toBe("market-pipeline")
    expect(resolveMarketArtName({ title: "Starter pack", department: "customer_success" })).toBe("market-support")
    expect(resolveMarketArtName({ title: "Starter pack", assetType: "knowledge_pack" })).toBe("market-compliance")
    expect(resolveMarketArtName({ title: "Untitled" })).toBe(MARKET_ART_FALLBACK)
    expect(resolveMarketArtName({})).toBe(MARKET_ART_FALLBACK)
  })

  it("never returns a department scene or a feature spot", () => {
    const art = resolveMarketArt({ title: "Sales team", department: "Sales" })
    expect(art.name).toMatch(/^market-/)
    expect(art.label).toBe("Pipeline")
  })
})
