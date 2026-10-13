import { describe, expect, it } from "vitest"
import { disconnectImpactLines, type DataRemovalPolicy } from "@/components/connectors/data-removal"

const base: DataRemovalPolicy = {
  dataRemoval: "off",
  memoriesIncluded: true,
  providerRevokeEnabled: false,
  providerRevokeVendors: ["hubspot", "salesforce", "slack"],
  deletionPropagationEnabled: false,
}

describe("disconnectImpactLines", () => {
  it("never promises deletion while removal is off", () => {
    const text = disconnectImpactLines(base, "HubSpot", "hubspot").join(" ")
    expect(text).toContain("not switched on yet")
    expect(text).not.toContain("permanently deleted")
    expect(text).toContain("not revoked inside HubSpot")
  })

  it("says test mode keeps data and lists what would be deleted", () => {
    const text = disconnectImpactLines({ ...base, dataRemoval: "test" }, "HubSpot", "hubspot").join(" ")
    expect(text).toContain("test mode")
    expect(text).toContain("would be deleted")
    expect(text).not.toContain("permanently deleted")
  })

  it("says permanent deletion and revoke only when both are on and supported", () => {
    const policy = { ...base, dataRemoval: "on" as const, providerRevokeEnabled: true }
    const hubspot = disconnectImpactLines(policy, "HubSpot", "hubspot").join(" ")
    expect(hubspot).toContain("permanently deleted")
    expect(hubspot).toContain("asks HubSpot to revoke")
    const zendesk = disconnectImpactLines(policy, "Zendesk", "zendesk").join(" ")
    expect(zendesk).toContain("not revoked inside Zendesk")
  })

  it("leaves memories out when lineage is off", () => {
    const text = disconnectImpactLines({ ...base, memoriesIncluded: false, dataRemoval: "on" }, "Notion", "notion").join(" ")
    expect(text).not.toContain("memories")
  })
})
