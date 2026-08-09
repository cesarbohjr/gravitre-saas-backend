import { describe, expect, it } from "vitest"
import {
  PACK_PLATFORM_SOURCE_TYPES,
  partitionConnectorChecklist,
  resolvePlatformSources,
} from "@/lib/marketplace-platform-sources"
import type { MarketplaceConnectorChecklistItem } from "@/types/api"

function item(
  connectorType: string,
  overrides: Partial<MarketplaceConnectorChecklistItem> = {},
): MarketplaceConnectorChecklistItem {
  return {
    connectorType,
    label: connectorType,
    required: false,
    connected: false,
    connectPath: `/connectors?type=${connectorType}`,
    ready: false,
    ...overrides,
  }
}

describe("marketplace platform sources", () => {
  it("maps executive and MSP packs to gravitre vendors", () => {
    expect(PACK_PLATFORM_SOURCE_TYPES["executive-intelligence-pack"]).toContain("fred")
    expect(PACK_PLATFORM_SOURCE_TYPES["executive-intelligence-pack"]).toContain("world_bank")
    expect(PACK_PLATFORM_SOURCE_TYPES["msp-intelligence-pack"]).toEqual(["nvd", "cisa_kev"])
  })

  it("partitions checklist into platform vs tenant apps", () => {
    const { platform, apps } = partitionConnectorChecklist([
      item("fred"),
      item("hubspot", { required: true }),
      item("nvd"),
      item("apollo"),
    ])
    expect(platform.map((i) => i.connectorType)).toEqual(["fred", "nvd"])
    expect(apps.map((i) => i.connectorType)).toEqual(["hubspot", "apollo"])
  })

  it("resolves executive platform sources with managed/active/pending labels", () => {
    const sources = resolvePlatformSources({
      packSlug: "executive-intelligence-pack",
      checklist: [item("fred", { connected: true, ready: true, label: "FRED" })],
      installed: false,
    })
    expect(sources.map((s) => s.connectorType)).toEqual([
      "fred",
      "sec_edgar",
      "world_bank",
      "oecd",
      "opencorporates",
    ])
    expect(sources.find((s) => s.connectorType === "fred")?.status).toBe("active")
    expect(sources.find((s) => s.connectorType === "sec_edgar")?.status).toBe("managed")
    expect(sources.find((s) => s.connectorType === "opencorporates")?.status).toBe("pending_license")
    expect(sources.find((s) => s.connectorType === "opencorporates")?.statusLabel).toBe(
      "Pending license",
    )
  })

  it("marks pack sources active after install even without checklist rows", () => {
    const sources = resolvePlatformSources({
      packSlug: "msp-intelligence-pack",
      checklist: [],
      installed: true,
    })
    expect(sources).toHaveLength(2)
    expect(sources.every((s) => s.status === "active")).toBe(true)
    expect(sources.every((s) => s.statusLabel === "Active")).toBe(true)
  })

  it("falls back to checklist platform items when pack has no map", () => {
    const sources = resolvePlatformSources({
      packSlug: "sales-intelligence-pack",
      checklist: [item("hubspot"), item("fred", { label: "FRED Macro" })],
    })
    expect(sources).toHaveLength(1)
    expect(sources[0]?.connectorType).toBe("fred")
    expect(sources[0]?.label).toBe("FRED Macro")
  })
})
