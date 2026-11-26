import { afterEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"
import { proxyToFastApi, syncWorkflowSchemaFromContract } from "@/lib/backend-proxy"
import { proxyRunAction, proxyRunStepAction } from "@/lib/run-action-proxy"
import { PRODUCTION_BACKEND_URL } from "@/lib/public-urls"

vi.mock("@/lib/supabase-server", () => ({
  createSupabaseServerClient: vi.fn(async () => ({
    auth: { getSession: async () => ({ data: { session: null } }) },
  })),
}))

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

function request(authenticated = true) {
  return new NextRequest("https://gravitre.app/api/runs/run-1/cancel?trace=synthetic", {
    method: "POST",
    headers: {
      ...(authenticated ? { authorization: "Bearer synthetic-only" } : {}),
      "x-org-id": "tenant-a", "x-environment": "synthetic", "content-type": "application/json",
      cookie: "must-not-forward", "x-admin-override": "must-not-forward",
    },
    body: JSON.stringify({ reason: "synthetic cancellation" }),
  })
}

function mockUpstream() {
  const fetch = vi.fn(async () => Response.json({ status: "cancelled" }))
  vi.stubGlobal("fetch", fetch)
  return fetch
}

function expectTenantHeaders(init: RequestInit) {
  const headers = new Headers(init.headers)
  expect(headers.get("authorization")).toBe("Bearer synthetic-only")
  expect(headers.get("x-org-id")).toBe("tenant-a")
  expect(headers.get("x-environment")).toBe("synthetic")
  expect(headers.has("cookie")).toBe(false)
  expect(headers.has("x-admin-override")).toBe(false)
  expect(init.cache).toBe("no-store")
}

describe("DEC-017 general proxy production routing", () => {
  it.each([
    ["production", "", PRODUCTION_BACKEND_URL],
    ["production", "https://api.gravitre.app", PRODUCTION_BACKEND_URL],
    ["production", "https://private.example.invalid/", "https://private.example.invalid"],
    ["development", "", "http://localhost:8000"],
  ])("uses the canonical origin in %s with configured origin %s", async (environment, configured, expected) => {
    vi.stubEnv("NODE_ENV", environment)
    vi.stubEnv("FASTAPI_BASE_URL", configured)
    const upstream = mockUpstream()
    const response = await proxyToFastApi(request(), "/api/runs/run-1/cancel")
    expect(response.status).toBe(200)
    expect(upstream).toHaveBeenCalledTimes(1)
    const [url, init] = upstream.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${expected}/api/runs/run-1/cancel?trace=synthetic`)
    expectTenantHeaders(init)
    expect(init.body).toBe(JSON.stringify({ reason: "synthetic cancellation" }))
  })

  it("syncs workflow schemas to the same production origin without an explicit variable", async () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = mockUpstream()
    await syncWorkflowSchemaFromContract(request(), "workflow-1")
    expect(upstream).toHaveBeenCalledTimes(1)
    const [url, init] = upstream.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${PRODUCTION_BACKEND_URL}/api/workflows/workflow-1/schema-sync/from-contract?trace=synthetic`)
    expect(init.method).toBe("POST")
    expectTenantHeaders(init)
  })

  it("retains the local-development schema-sync opt-in", async () => {
    vi.stubEnv("NODE_ENV", "development")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = mockUpstream()
    await syncWorkflowSchemaFromContract(request(), "workflow-1")
    expect(upstream).not.toHaveBeenCalled()
  })
})

describe.each([
  ["run", (req: NextRequest) => proxyRunAction(req, "run-1", "cancel"), "/api/runs/run-1/cancel"],
  ["step", (req: NextRequest) => proxyRunStepAction(req, "run-1", "step-1", "retry"), "/api/runs/run-1/steps/step-1/retry"],
] as const)("DEC-017 %s action routing", (_kind, invoke, path) => {
  it("uses the production resolver and preserves the authenticated tenant", async () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = mockUpstream()
    const response = await invoke(request())
    expect(response.status).toBe(200)
    expect(upstream).toHaveBeenCalledTimes(1)
    const [url, init] = upstream.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${PRODUCTION_BACKEND_URL}${path}`)
    expectTenantHeaders(init)
    expect(init.method).toBe("POST")
  })

  it("retains the development configuration error without calling a backend", async () => {
    vi.stubEnv("NODE_ENV", "development")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = mockUpstream()
    expect((await invoke(request())).status).toBe(503)
    expect(upstream).not.toHaveBeenCalled()
  })

  it("rejects an unauthenticated call before backend dispatch", async () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = mockUpstream()
    expect((await invoke(request(false))).status).toBe(401)
    expect(upstream).not.toHaveBeenCalled()
  })
})
