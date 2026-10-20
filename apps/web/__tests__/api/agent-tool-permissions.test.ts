import { beforeEach, describe, expect, it, vi } from "vitest"

const { apiFetch, fetcher } = vi.hoisted(() => ({ apiFetch: vi.fn(), fetcher: vi.fn() }))
vi.mock("@/lib/fetcher", () => ({ apiFetch, fetcher }))

import { agentToolPermissionsApi } from "@/lib/agent-tool-permissions"

describe("agent connector permission API", () => {
  beforeEach(() => {
    apiFetch.mockReset()
    fetcher.mockReset()
  })

  it("reads only the selected agent's grants", async () => {
    fetcher.mockResolvedValueOnce([])
    await agentToolPermissionsApi.list("agent/one")
    expect(fetcher).toHaveBeenCalledWith("/api/agents/agent%2Fone/tool-permissions")
  })

  it("grants exact scoped permission with expiry", async () => {
    apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ id: "grant-1" }) })
    const grant = { connectorId: "connector-1", scopes: ["contacts.read"], expiresAt: "2026-10-19T00:00:00Z" }
    await agentToolPermissionsApi.grant("agent-1", grant)
    expect(apiFetch).toHaveBeenCalledWith("/api/agents/agent-1/tool-permissions", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(grant),
    })
  })

  it("accepts a successful 204 revoke without parsing an empty body", async () => {
    const json = vi.fn()
    apiFetch.mockResolvedValueOnce({ ok: true, status: 204, json })
    await agentToolPermissionsApi.revoke("agent-1", "grant-1")
    expect(json).not.toHaveBeenCalled()
    expect(apiFetch).toHaveBeenCalledWith("/api/agents/agent-1/tool-permissions/grant-1", { method: "DELETE" })
  })

  it("surfaces backend authorization denial", async () => {
    apiFetch.mockResolvedValueOnce({
      ok: false, status: 403, json: async () => ({ detail: "Admin required" }),
    })
    await expect(agentToolPermissionsApi.revoke("agent-1", "grant-1")).rejects.toThrow("Admin required")
  })
})
