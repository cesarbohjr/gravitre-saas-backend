import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

/**
 * Phase 5: one write path for goals. With GOALS_BACKEND_WRITES=true every goal
 * read and write goes to the FastAPI goals API; without it the routes keep
 * writing through Supabase exactly as before.
 */

const proxyToFastApi = vi.fn()
const from = vi.fn()

vi.mock("@/lib/backend-proxy", () => ({
  proxyToFastApi: (...args: unknown[]) => proxyToFastApi(...args),
}))

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseRouteClient: () => ({ from }),
  resolveOrgId: async () => "org-1",
}))

function req(method: string, url: string, body?: unknown) {
  return new Request(url, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }) as never
}

const params = { params: Promise.resolve({ id: "goal-1" }) }

describe("goals routes write path", () => {
  beforeEach(() => {
    proxyToFastApi.mockReset()
    proxyToFastApi.mockResolvedValue(new Response(JSON.stringify({ goal: { id: "goal-1" } }), { status: 201 }))
    from.mockReset()
  })
  afterEach(() => {
    delete process.env.GOALS_BACKEND_WRITES
  })

  it("proxies every goal route to FastAPI when the flag is on", async () => {
    process.env.GOALS_BACKEND_WRITES = "true"
    const list = await import("@/app/api/goals/route")
    const one = await import("@/app/api/goals/[id]/route")
    await list.GET(req("GET", "https://gravitre.app/api/goals"))
    await list.POST(req("POST", "https://gravitre.app/api/goals", { objective: "Grow" }))
    await one.GET(req("GET", "https://gravitre.app/api/goals/goal-1"), params)
    await one.PATCH(req("PATCH", "https://gravitre.app/api/goals/goal-1", { status: "active" }), params)
    expect(proxyToFastApi.mock.calls.map((c) => c[1])).toEqual([
      "/api/goals",
      "/api/goals",
      "/api/goals/goal-1",
      "/api/goals/goal-1",
    ])
    expect(from).not.toHaveBeenCalled()
  })

  it("keeps the Supabase path when the flag is off", async () => {
    const insert = vi.fn(() => ({ select: () => ({ single: async () => ({ data: { id: "g", org_id: "org-1" }, error: null }) }) }))
    from.mockReturnValue({ insert })
    const list = await import("@/app/api/goals/route")
    const res = await list.POST(req("POST", "https://gravitre.app/api/goals", { objective: "Grow" }))
    expect(res.status).toBe(201)
    expect(proxyToFastApi).not.toHaveBeenCalled()
    expect(from).toHaveBeenCalledWith("goals")
  })
})
