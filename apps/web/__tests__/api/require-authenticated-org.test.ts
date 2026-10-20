import { describe, expect, it } from "vitest"
import { NextRequest } from "next/server"

import { requireAuthenticatedOrg } from "@/lib/supabase/server"

const ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

type MembershipRow = { org_id: string; role: string }

function makeSupabase(options: {
  userId: string | null
  memberships: MembershipRow[]
}) {
  const { userId, memberships } = options
  return {
    auth: {
      getUser: async () => ({
        data: { user: userId ? { id: userId } : null },
        error: null,
      }),
    },
    from: (table: string) => {
      if (table !== "organization_members") {
        throw new Error(`unexpected table ${table}`)
      }
      const filters: Record<string, string> = {}
      const builder: Record<string, unknown> = {}
      builder.select = () => builder
      builder.eq = (key: string, value: string) => {
        filters[key] = value
        return builder
      }
      builder.order = () => builder
      builder.limit = () => builder
      builder.maybeSingle = async () => {
        let rows = [...memberships]
        if (filters.org_id) {
          rows = rows.filter((row) => row.org_id === filters.org_id)
        }
        return { data: rows[0] ?? null, error: null }
      }
      return builder
    },
  }
}

describe("requireAuthenticatedOrg", () => {
  it("returns 401 when no user session", async () => {
    const req = new NextRequest(`https://gravitre.app/api/sessions?org_id=${ORG_A}`)
    const supabase = makeSupabase({ userId: null, memberships: [] })
    const result = await requireAuthenticatedOrg(supabase as never, req)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.response.status).toBe(401)
  })

  it("returns 403 when user is not a member of requested org", async () => {
    const req = new NextRequest(`https://gravitre.app/api/sessions?org_id=${ORG_B}`, {
      headers: { authorization: "Bearer jwt" },
    })
    const supabase = makeSupabase({
      userId: "user-1",
      memberships: [{ org_id: ORG_A, role: "member" }],
    })
    const result = await requireAuthenticatedOrg(supabase as never, req)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.response.status).toBe(403)
  })

  it("returns org context for members", async () => {
    const req = new NextRequest(`https://gravitre.app/api/sessions?org_id=${ORG_A}`, {
      headers: { authorization: "Bearer jwt", "x-org-id": ORG_A },
    })
    const supabase = makeSupabase({
      userId: "user-1",
      memberships: [{ org_id: ORG_A, role: "member" }],
    })
    const result = await requireAuthenticatedOrg(supabase as never, req)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.context.orgId).toBe(ORG_A)
      expect(result.context.role).toBe("member")
    }
  })

  it("returns admin role from membership row", async () => {
    const req = new NextRequest("https://gravitre.app/api/sessions", {
      headers: { authorization: "Bearer jwt" },
    })
    const supabase = makeSupabase({
      userId: "admin-1",
      memberships: [{ org_id: ORG_A, role: "admin" }],
    })
    const result = await requireAuthenticatedOrg(supabase as never, req)
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.context.role).toBe("admin")
  })
})
