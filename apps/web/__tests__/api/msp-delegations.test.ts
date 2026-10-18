import { beforeEach, describe, expect, it, vi } from "vitest"

const apiFetch = vi.fn()
vi.mock("@/lib/fetcher", () => ({ apiFetch }))

import { mspDelegationsApi } from "@/lib/msp-delegations"

describe("MSP delegation API contracts", () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ customer_org_id: "customer-a", grants: [], audit: [], provider: null, provider_members: [] }),
    })
  })

  it("reads only the requested customer management path", async () => {
    await mspDelegationsApi.management("customer-a")
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/msp/delegations/customer/customer-a/management",
      undefined,
    )
  })

  it("sends an explicit action-scoped grant, not an org switch", async () => {
    const body = {
      provider_org_id: "provider",
      customer_org_id: "customer",
      grantee_user_id: "user",
      tier: 1 as const,
      actions: ["account.health.read" as const],
      expires_at: "2026-10-19T00:00:00.000Z",
    }
    await mspDelegationsApi.create(body)
    expect(apiFetch).toHaveBeenCalledWith("/api/msp/delegations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  })

  it("scopes revoke to the specified customer", async () => {
    await mspDelegationsApi.revoke("grant-1", "customer-a")
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/msp/delegations/grant-1/revoke?customer_org_id=customer-a",
      { method: "POST" },
    )
  })

  it("propagates denied access instead of pretending success", async () => {
    apiFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Customer owner required" }),
    })
    await expect(mspDelegationsApi.management("customer-b"))
      .rejects.toThrow("Customer owner required")
  })
})
