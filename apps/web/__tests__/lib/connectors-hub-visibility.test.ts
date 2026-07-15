import { describe, expect, it } from "vitest"
import { isConnectorsHubHidden } from "@/lib/connectors"

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
