import { describe, expect, it } from "vitest"
import { identityDepartmentFor, listingKindFor } from "@/lib/listing-identity"
import { listingReadiness, matchesReadiness } from "@/lib/listing-readiness"
import { listingMeta, installedDescription } from "@/lib/listing-meta"
import type { MarketplaceAssetSummary } from "@/types/api"

const base: MarketplaceAssetSummary = {
  id: "a1",
  slug: "cash-flow-analyst",
  title: "Cash Flow Analyst",
  assetType: "ai_agent",
  department: "Finance",
  tags: [],
  pricingType: "free",
  canInstall: true,
  installed: false,
  connectorChecklist: [],
  connectorsReady: true,
  requiredConnectorsConnected: 0,
  requiredConnectorsTotal: 0,
}

const app = (label: string, connected: boolean, extra: Record<string, unknown> = {}) => ({
  connectorType: label.toLowerCase(),
  label,
  required: true,
  connected,
  connectPath: "/connectors",
  ready: connected,
  ...extra,
})

describe("listing identity", () => {
  it("keeps Support and HR as their own departments", () => {
    expect(identityDepartmentFor("Support").id).toBe("support")
    expect(identityDepartmentFor("People Ops").id).toBe("hr")
    expect(identityDepartmentFor("customer_success").id).toBe("customer_success")
    expect(identityDepartmentFor(null).id).toBe("general")
    expect(identityDepartmentFor("Finance").color).toBe("#4E7350")
  })

  it("maps every asset type to one of five kinds", () => {
    expect(listingKindFor("ai_agent")).toBe("agent")
    expect(listingKindFor("department_pack")).toBe("pack")
    expect(listingKindFor("connector_config")).toBe("connector")
    expect(listingKindFor("something_new")).toBe("pack")
  })
})

describe("listing readiness", () => {
  it("asks to connect the missing app, with a typed connect link", () => {
    const readiness = listingReadiness({ ...base, connectorChecklist: [app("HubSpot", false)] }, { canInstall: true })
    expect(readiness.state).toBe("connect")
    expect(readiness.label).toBe("Needs HubSpot")
    expect(readiness.action).toEqual({ kind: "connect", label: "Connect", href: "/connectors?connect=hubspot" })
  })

  it("asks for review when a connected app reports a plan limitation", () => {
    const readiness = listingReadiness(
      { ...base, connectorChecklist: [app("Apollo", true, { discoveryLimitation: "needs search API" })] },
      { canInstall: true },
    )
    expect(readiness.state).toBe("review")
    expect(readiness.label).toBe("Needs Apollo search API")
  })

  it("never offers Install to someone who cannot install", () => {
    expect(listingReadiness(base, { canInstall: true }).action.kind).toBe("install")
    expect(listingReadiness(base, { canInstall: false }).action.kind).toBe("details")
  })

  it("says Connected for an installed connector and Installed otherwise", () => {
    expect(listingReadiness({ ...base, installed: true }, { canInstall: true }).label).toBe("Installed")
    expect(listingReadiness({ ...base, assetType: "connector_config", installed: true }, { canInstall: true }).label).toBe("Connected")
  })

  it("does not claim readiness when setup requirements are not reported", () => {
    const readiness = listingReadiness({ ...base, connectorChecklist: undefined as never }, { canInstall: true })
    expect(readiness.state).toBe("unknown")
    expect(matchesReadiness(readiness, "ready")).toBe(false)
  })
})

describe("listing meta", () => {
  it("summarizes pack contents and apps from catalog data only", () => {
    const pack = {
      ...base,
      assetType: "department_pack",
      department: "Support",
      packItems: [
        { sortOrder: 0, required: true, child: { id: "1", slug: "a", title: "A", assetType: "ai_agent" } },
        { sortOrder: 1, required: true, child: { id: "2", slug: "w", title: "W", assetType: "workflow" } },
        { sortOrder: 2, required: true, child: { id: "3", slug: "x", title: "X", assetType: "workflow" } },
      ],
    } as MarketplaceAssetSummary
    expect(listingMeta(pack)).toBe("1 agent · 2 workflows")
    expect(installedDescription(pack)).toBe("1 agent and 2 workflows are ready in Support.")
    expect(listingMeta({ ...base, connectorChecklist: [app("Apollo", false), app("HubSpot", true)] })).toBe("Uses Apollo, HubSpot")
  })
})
