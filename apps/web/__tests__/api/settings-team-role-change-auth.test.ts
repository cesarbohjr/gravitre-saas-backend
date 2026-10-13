import { beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"

/**
 * PATCH /api/settings/team changed roles with no admin check, and wrote
 * organization_members directly. The only write policy on that table let a user
 * update their own row, so any member could promote themselves to owner here.
 * Role changes now require an admin caller and go through the backend.
 */

const ORG = "11111111-1111-4111-8111-111111111111"

type Row = Record<string, unknown> | null
const state: {
  callerId: string | null
  callerRole: string | null
  targetUser: Row
  membership: Row
  usersUpdate: ReturnType<typeof vi.fn>
} = {
  callerId: "caller",
  callerRole: "member",
  targetUser: { auth_user_id: "target" },
  membership: { id: "mem-1" },
  usersUpdate: vi.fn(),
}

function builder(table: string) {
  const filters: Record<string, unknown> = {}
  let mode: "select" | "update" = "select"
  const b: Record<string, unknown> = {}
  b.select = () => b
  b.eq = (k: string, v: unknown) => {
    filters[k] = v
    return b
  }
  b.update = (patch: unknown) => {
    mode = "update"
    state.usersUpdate(table, patch)
    return b
  }
  b.maybeSingle = async () => {
    if (table === "organization_members" && filters.user_id === state.callerId) {
      return { data: state.callerRole ? { role: state.callerRole } : null }
    }
    if (table === "organization_members") return { data: state.membership }
    if (table === "users") return { data: state.targetUser }
    return { data: null }
  }
  b.single = async () =>
    mode === "update" ? { data: { id: "u1", auth_user_id: "target", role: "admin" }, error: null } : { data: null }
  return b
}

const supabase = {
  auth: { getUser: async () => ({ data: { user: state.callerId ? { id: state.callerId } : null } }) },
  from: (table: string) => builder(table),
}

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseRouteClient: () => supabase,
  resolveOrgId: async () => ORG,
}))
vi.mock("@/lib/supabase/demo-bootstrap", () => ({ ensureDemoDataForOrg: async () => undefined }))

const callFastApiAsCaller = vi.fn()
vi.mock("@/lib/backend-proxy", () => ({
  proxyToFastApi: vi.fn(),
  callFastApiAsCaller: (...args: unknown[]) => callFastApiAsCaller(...args),
}))

function patch(body: unknown) {
  return new NextRequest("https://gravitre.app/api/settings/team", {
    method: "PATCH",
    headers: { authorization: "Bearer jwt", "content-type": "application/json" },
    body: JSON.stringify(body),
  })
}

describe("PATCH /api/settings/team role changes", () => {
  beforeEach(() => {
    state.callerId = "caller"
    state.callerRole = "member"
    state.targetUser = { auth_user_id: "target" }
    state.membership = { id: "mem-1" }
    state.usersUpdate = vi.fn()
    callFastApiAsCaller.mockReset()
    callFastApiAsCaller.mockResolvedValue({ ok: true, status: 200, payload: {} })
  })

  it("refuses a member promoting anyone, including themselves", async () => {
    const { PATCH } = await import("@/app/api/settings/team/route")
    const res = await PATCH(patch({ id: "u1", role: "owner" }))
    expect(res.status).toBe(403)
    expect(callFastApiAsCaller).not.toHaveBeenCalled()
    expect(state.usersUpdate).not.toHaveBeenCalled()
  })

  it("refuses an anonymous caller", async () => {
    state.callerId = null
    const { PATCH } = await import("@/app/api/settings/team/route")
    const res = await PATCH(patch({ id: "u1", role: "admin" }))
    expect(res.status).toBe(401)
    expect(state.usersUpdate).not.toHaveBeenCalled()
  })

  it("does not let an admin assign ownership here", async () => {
    state.callerRole = "admin"
    const { PATCH } = await import("@/app/api/settings/team/route")
    const res = await PATCH(patch({ id: "u1", role: "owner" }))
    expect(res.status).toBe(400)
    expect(callFastApiAsCaller).not.toHaveBeenCalled()
  })

  it("sends an admin's role change to the backend before updating the user row", async () => {
    state.callerRole = "admin"
    const { PATCH } = await import("@/app/api/settings/team/route")
    const res = await PATCH(patch({ id: "u1", role: "admin" }))
    expect(res.status).toBe(200)
    expect(callFastApiAsCaller).toHaveBeenCalledWith(
      expect.anything(),
      `/api/organizations/${ORG}/members/target`,
      "PATCH",
      { role: "admin" },
      ORG,
    )
    expect(state.usersUpdate).toHaveBeenCalledWith("users", expect.objectContaining({ role: "admin" }))
    // organization_members is never written from the web app.
    expect(state.usersUpdate).not.toHaveBeenCalledWith("organization_members", expect.anything())
  })

  it("leaves the user row alone when the backend refuses", async () => {
    state.callerRole = "admin"
    callFastApiAsCaller.mockResolvedValue({ ok: false, status: 400, payload: { detail: "last admin" } })
    const { PATCH } = await import("@/app/api/settings/team/route")
    const res = await PATCH(patch({ id: "u1", role: "member" }))
    expect(res.status).toBe(400)
    expect(state.usersUpdate).not.toHaveBeenCalled()
  })

  it("still lets a member edit a name without a role change", async () => {
    const { PATCH } = await import("@/app/api/settings/team/route")
    const res = await PATCH(patch({ id: "u1", fullName: "New Name" }))
    expect(res.status).toBe(200)
    expect(callFastApiAsCaller).not.toHaveBeenCalled()
  })
})
