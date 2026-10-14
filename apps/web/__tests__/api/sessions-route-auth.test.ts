import { beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest, NextResponse } from "next/server"

const ORG_MEMBER = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const ORG_OTHER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

const authState: {
  mode: "anonymous" | "member" | "nonmember" | "admin"
  dbError: boolean
} = {
  mode: "member",
  dbError: false,
}

function authResult() {
  if (authState.mode === "anonymous") {
    return {
      ok: false as const,
      response: NextResponse.json({ error: "Unauthorized" }, { status: 401 }),
    }
  }
  if (authState.mode === "nonmember") {
    return {
      ok: false as const,
      response: NextResponse.json({ error: "Forbidden" }, { status: 403 }),
    }
  }
  return {
    ok: true as const,
    context: {
      userId: authState.mode === "admin" ? "admin-user" : "member-user",
      orgId: ORG_MEMBER,
      role: authState.mode === "admin" ? "admin" : "member",
    },
  }
}

function queryBuilder() {
  const b: Record<string, unknown> = {}
  b.select = () => b
  b.eq = () => b
  b.or = () => b
  b.order = () => b
  b.limit = () => b
  b.insert = () => b
  b.single = async () =>
    authState.dbError
      ? { data: null, error: { message: "relation sessions does not exist" } }
      : {
          data: {
            id: "sess-1",
            org_id: ORG_MEMBER,
            title: "Operator Session",
            status: "active",
            context_entity_type: null,
            context_entity_id: null,
            created_at: new Date().toISOString(),
          },
          error: null,
        }
  b.then = (resolve: (v: unknown) => unknown) =>
    resolve(
      authState.dbError
        ? { data: null, error: { message: "permission denied for table runs" } }
        : { data: [], error: null },
    )
  return b
}

const supabase = {
  from: () => queryBuilder(),
}

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseRouteClient: () => supabase,
  requireAuthenticatedOrg: async () => authResult(),
}))

vi.mock("@/lib/supabase/demo-bootstrap", () => ({
  ensureDemoDataForOrg: async () => undefined,
}))

function getRequest(url = "https://gravitre.app/api/sessions") {
  return new NextRequest(url, {
    method: "GET",
    headers: { authorization: "Bearer jwt" },
  })
}

function postRequest(body: Record<string, unknown> = {}) {
  return new NextRequest("https://gravitre.app/api/sessions", {
    method: "POST",
    headers: { authorization: "Bearer jwt", "content-type": "application/json" },
    body: JSON.stringify(body),
  })
}

describe("/api/sessions auth and error handling", () => {
  beforeEach(() => {
    authState.mode = "member"
    authState.dbError = false
  })

  it("GET returns 401 for anonymous callers", async () => {
    authState.mode = "anonymous"
    const { GET } = await import("@/app/api/sessions/route")
    const res = await GET(getRequest())
    expect(res.status).toBe(401)
  })

  it("GET returns 403 for authenticated non-members", async () => {
    authState.mode = "nonmember"
    const { GET } = await import("@/app/api/sessions/route")
    const res = await GET(getRequest(`https://gravitre.app/api/sessions?org_id=${ORG_OTHER}`))
    expect(res.status).toBe(403)
  })

  it("GET succeeds for org members", async () => {
    const { GET } = await import("@/app/api/sessions/route")
    const res = await GET(getRequest())
    expect(res.status).toBe(200)
    const body = (await res.json()) as { activeSessions: number; recentActivity: unknown[] }
    expect(body.activeSessions).toBe(0)
    expect(Array.isArray(body.recentActivity)).toBe(true)
  })

  it("GET succeeds for org admins", async () => {
    authState.mode = "admin"
    const { GET } = await import("@/app/api/sessions/route")
    const res = await GET(getRequest())
    expect(res.status).toBe(200)
  })

  it("GET sanitizes database errors", async () => {
    authState.dbError = true
    const { GET } = await import("@/app/api/sessions/route")
    const res = await GET(getRequest())
    expect(res.status).toBe(503)
    const body = (await res.json()) as { error: string }
    expect(body.error).toBe("Failed to load sessions")
    expect(body.error).not.toMatch(/permission denied|relation/)
  })

  it("POST returns 401 for anonymous callers", async () => {
    authState.mode = "anonymous"
    const { POST } = await import("@/app/api/sessions/route")
    const res = await POST(postRequest())
    expect(res.status).toBe(401)
  })

  it("POST creates session for members with sanitized insert errors", async () => {
    authState.dbError = true
    const { POST } = await import("@/app/api/sessions/route")
    const res = await POST(postRequest({ title: "Test" }))
    expect(res.status).toBe(503)
    const body = (await res.json()) as { error: string }
    expect(body.error).toBe("Failed to create session")
  })
})
