import { describe, expect, it } from "vitest"
import {
  isConnectorsHubCatalogVendor,
  isConnectorsHubHidden,
  listAvailableConnectors,
  resolveConnectorVendorSlug,
  shouldShowConnectedConnectorOnHub,
} from "@/lib/connectors"

describe("isConnectorsHubHidden", () => {
  it("hides gravitree_managed / platform_only catalog vendors", () => {
    expect(isConnectorsHubHidden("fred")).toBe(true)
    expect(isConnectorsHubHidden("SEC EDGAR")).toBe(true)
    expect(isConnectorsHubHidden("nvd")).toBe(true)
    expect(isConnectorsHubHidden("cisa_kev")).toBe(true)
    expect(isConnectorsHubHidden("world_bank")).toBe(true)
    expect(isConnectorsHubHidden("oecd")).toBe(true)
    expect(isConnectorsHubHidden("opencorporates")).toBe(true)
  })

  it("keeps customer-owned connectors visible on the hub", () => {
    expect(isConnectorsHubHidden("hubspot")).toBe(false)
    expect(isConnectorsHubHidden("google_search_console")).toBe(false)
    expect(isConnectorsHubHidden("apollo")).toBe(false)
    expect(isConnectorsHubHidden("zoominfo")).toBe(false)
  })

  it("hides rows flagged gravitree_managed in config even if catalog miss", () => {
    expect(isConnectorsHubHidden("unknown_vendor", { auth_mode: "gravitree_managed" })).toBe(true)
    expect(isConnectorsHubHidden("unknown_vendor", { authMode: "customer_owned" })).toBe(false)
  })
})

describe("connected connector hub visibility", () => {
  it("keeps catalog vendors in the available strip", () => {
    const availableKeys = new Set(listAvailableConnectors().map((entry) => entry.vendorKey))
    for (const vendor of [
      "marketo",
      "segment",
      "google_analytics",
      "google_search_console",
      "constant_contact",
      "semrush",
      "ahrefs",
    ]) {
      expect(availableKeys.has(vendor)).toBe(true)
    }
  })

  it("recognizes catalog vendors", () => {
    expect(isConnectorsHubCatalogVendor("hubspot")).toBe(true)
    expect(isConnectorsHubCatalogVendor("Marketo")).toBe(true)
    expect(isConnectorsHubCatalogVendor("custom")).toBe(false)
    expect(isConnectorsHubCatalogVendor("")).toBe(false)
  })

  it("resolves vendor slug from API vendor or legacy type field", () => {
    expect(resolveConnectorVendorSlug("hubspot", undefined)).toBe("hubspot")
    expect(resolveConnectorVendorSlug(undefined, "google_analytics")).toBe("google_analytics")
    expect(resolveConnectorVendorSlug("", "")).toBe("")
  })

  it("hides rows without a vendor slug, staged stubs, and non-catalog types", () => {
    expect(shouldShowConnectedConnectorOnHub("")).toBe(false)
    expect(shouldShowConnectedConnectorOnHub("custom")).toBe(false)
    expect(shouldShowConnectedConnectorOnHub("acme_tools")).toBe(false)
    expect(
      shouldShowConnectedConnectorOnHub("hubspot", { staged: true }, undefined, "needs_connection"),
    ).toBe(false)
    expect(shouldShowConnectedConnectorOnHub("hubspot")).toBe(true)
    expect(shouldShowConnectedConnectorOnHub("Constant Contact")).toBe(true)
    expect(shouldShowConnectedConnectorOnHub("partner_vendor", undefined, new Set(["partner_vendor"]))).toBe(
      true,
    )
    expect(shouldShowConnectedConnectorOnHub("fred")).toBe(false)
  })
})
