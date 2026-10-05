// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import { MarketplaceFeaturedOutcome } from "@/components/marketplace/marketplace-featured-outcome"
import type { MarketplaceAssetSummary } from "@/types/api"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("Marketplace featured catalog outcome", () => {
  it("previews the real asset and derives contents without inventing execution or claims", () => {
    const asset: MarketplaceAssetSummary = {
      id: "pack-real", slug: "msp-operations-pack", title: "MSP Operations Pack",
      description: "Service coordination and runbooks.", assetType: "department_pack",
      department: "Operations", tags: [], pricingType: "free", canInstall: true,
      installed: false, connectorChecklist: [], connectorsReady: true,
      requiredConnectorsConnected: 0, requiredConnectorsTotal: 0,
      packItems: [{ sortOrder: 0, required: true, child: { id: "child-real", slug: "runbooks", title: "Service Runbooks", assetType: "knowledge_pack" } }],
    }
    const onPreview = vi.fn()
    const container = document.createElement("div")
    const root = createRoot(container)
    try {
      act(() => root.render(<MarketplaceFeaturedOutcome asset={asset} onPreview={onPreview} />))
      expect(container.textContent).toContain("MSP Operations Pack")
      expect(container.textContent).toContain("Service Runbooks")
      expect(container.textContent).toContain("1 included component · 0 connectors")
      expect(container.textContent).not.toMatch(/verified|live|Run this Play|18 Plays/i)
      act(() => container.querySelector("button")!.click())
      expect(onPreview).toHaveBeenCalledExactlyOnceWith(asset)
    } finally {
      act(() => root.unmount())
    }
  })
})
