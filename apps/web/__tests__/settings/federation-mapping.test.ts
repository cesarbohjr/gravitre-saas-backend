import { describe, expect, it } from "vitest"
import type { FederationConnectorGrant, FederationHandoff } from "@/types/api"
import {
  FEDERATION_TABS,
  awaitsOurConsent,
  canRespondToHandoff,
  federationStats,
  grantPermissions,
  partnerLabel,
  type FederationPartnershipRow,
} from "@/lib/settings-api/federation"

const ME = "org-me"
const partnership = (over: Partial<FederationPartnershipRow>): FederationPartnershipRow => ({
  id: "p",
  orgAId: ME,
  orgBId: "org-partner-123456",
  currentOrgId: ME,
  partnerOrgId: "org-partner-123456",
  invitedByOrgId: ME,
  status: "active",
  initiatorConsentAt: null,
  partnerConsentAt: null,
  createdAt: null,
  updatedAt: null,
  ...over,
})

describe("Federation mapping", () => {
  it("counts active, pending, open handoffs and all partnerships", () => {
    const stats = federationStats(
      [partnership({ id: "1" }), partnership({ id: "2", status: "pending_partner" }), partnership({ id: "3", status: "revoked" })],
      [
        { status: "pending_receiver" } as FederationHandoff,
        { status: "accepted" } as FederationHandoff,
        { status: "completed" } as FederationHandoff,
      ],
    )
    expect(stats).toEqual({ active: 1, pending: 1, openHandoffs: 2, total: 3 })
  })

  it("labels partners by real name, else a short org id", () => {
    expect(partnerLabel(partnership({ partnerOrgName: "Acme" }))).toBe("Acme")
    expect(partnerLabel(partnership({ partnerOrgName: null }))).toBe("Org org-part")
  })

  it("only asks for our consent on invitations a partner sent", () => {
    expect(awaitsOurConsent(partnership({ status: "pending_partner", invitedByOrgId: "org-partner-123456" }), ME)).toBe(true)
    expect(awaitsOurConsent(partnership({ status: "pending_partner" }), ME)).toBe(false)
  })

  it("lets only the receiver answer a handoff and only the grantor revoke", () => {
    const h = { status: "pending_receiver", receiverOrgId: ME } as FederationHandoff
    expect(canRespondToHandoff(h, ME)).toBe(true)
    expect(canRespondToHandoff(h, "someone-else")).toBe(false)
    const g = { status: "active", grantorOrgId: ME, granteeOrgId: "x" } as FederationConnectorGrant
    expect(grantPermissions(g, ME)).toMatchObject({ canRevoke: true, canAccept: false, direction: "outgoing" })
  })

  it("has the three design tabs with their empty states", () => {
    expect(FEDERATION_TABS.map((t) => t.label)).toEqual(["Handoffs", "Connector grants", "Delegated tasks"])
    expect(FEDERATION_TABS[0].emptyTitle).toBe("No handoffs yet")
  })
})
