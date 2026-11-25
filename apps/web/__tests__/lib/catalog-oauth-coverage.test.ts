import { describe, expect, it } from "vitest"
import { CONNECTOR_CATALOG, isManagedConnectorVendor, isShippedConnector } from "@/lib/connectors"

describe("catalog dependency OAuth coverage", () => {
  it.each(["bamboohr", "greenhouse", "ahrefs", "freshservice", "gong", "hibob", "cal_com", "linear", "gitlab", "shopify", "paypal", "meta_marketing"])(
    "%s has one Gravitre OAuth entry rather than a duplicate or API-key form", (vendor) => {
      const entries = CONNECTOR_CATALOG.filter((entry) => entry.vendorKey === vendor)
      expect(entries).toHaveLength(1)
      expect(entries[0].authType).toBe("oauth")
      expect(entries[0].credentialModel).toBe("oauth2")
      expect(isManagedConnectorVendor(vendor)).toBe(true)
    },
  )

  it("preserves the native Slack, Google and Clio paths", () => {
    for (const vendor of ["slack", "google_ads", "google_analytics", "clio"]) {
      expect(CONNECTOR_CATALOG.filter((entry) => entry.vendorKey === vendor)).toHaveLength(1)
      expect(isManagedConnectorVendor(vendor)).toBe(false)
    }
  })

  it("keeps Ahrefs customer subscription ownership and exposes implemented read paths", () => {
    expect(CONNECTOR_CATALOG.find((entry) => entry.vendorKey === "ahrefs")?.authMode).toBe("byo_required")
    for (const vendor of ["bamboohr", "greenhouse", "ahrefs", "freshservice", "linear", "gitlab"]) {
      const entry = CONNECTOR_CATALOG.find((candidate) => candidate.vendorKey === vendor)!
      expect(entry.shipped).toBe(true)
      expect(isShippedConnector(entry)).toBe(true)
    }
  })
})
