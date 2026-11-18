import { afterEach, describe, expect, it, vi } from "vitest"
import { forwardAuthHeaders, proxyVoiceJson, voiceFastApiBase } from "@/lib/voice-api-proxy"
import { NextRequest } from "next/server"
import { PRODUCTION_BACKEND_URL } from "@/lib/public-urls"

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe("DEC-017 production voice API wiring", () => {
  it("routes to canonical Railway backend when deployed without FASTAPI_BASE_URL", () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    expect(voiceFastApiBase()).toBe(PRODUCTION_BACKEND_URL)
    expect(voiceFastApiBase()).not.toContain("localhost")
  })

  it("resolves live custom api.gravitre.app alias to the canonical backend", () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "https://api.gravitre.app")
    expect(voiceFastApiBase()).toBe(PRODUCTION_BACKEND_URL)
  })

  it("retains explicitly configured private backend origins", () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "https://backend.example.invalid/")
    expect(voiceFastApiBase()).toBe("https://backend.example.invalid")
  })

  it("preserves localhost only for explicit local development without an origin", () => {
    vi.stubEnv("NODE_ENV", "development")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    expect(voiceFastApiBase()).toBe("http://localhost:8000")
  })
})

describe("DEC-016 voice proxy tenant and approval header integrity", () => {
  it("forwards authorization, organization, environment and audio accept contract", () => {
    const request = new NextRequest("https://gravitre.app/api/voice/session/turn", {
      headers: {
        authorization: "Bearer qa-only-synthetic",
        "x-org-id": "11111111-1111-4111-8111-111111111111",
        "x-environment": "production",
        "x-gravitre-qa-force-voice-error": "synthetic-only",
      },
    })
    const forwarded = forwardAuthHeaders(request, { accept: "application/x-ndjson" })
    expect(forwarded.get("authorization")).toBe("Bearer qa-only-synthetic")
    expect(forwarded.get("x-org-id")).toBe("11111111-1111-4111-8111-111111111111")
    expect(forwarded.get("x-environment")).toBe("production")
    expect(forwarded.get("accept")).toBe("application/x-ndjson")
    expect(forwarded.get("x-gravitre-qa-force-voice-error")).toBe("synthetic-only")
    expect(forwarded.has("cookie")).toBe(false)
  })

  it("does not fabricate caller authorization or tenant headers when missing", () => {
    const request = new NextRequest("https://gravitre.app/api/voice/session/turn")
    const forwarded = forwardAuthHeaders(request)
    expect(forwarded.has("authorization")).toBe(false)
    expect(forwarded.has("x-org-id")).toBe(false)
    expect(forwarded.has("x-environment")).toBe(false)
  })
})

describe("QA00 real request proxy boundary (synthetic, no provider calls)", () => {
  it("forwards only the authenticated tenant context to the canonical API", async () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = vi.fn(async () => Response.json(
      { org_id: "tenant-a", environment: "synthetic", status: "ok" },
      { status: 200 },
    ))
    vi.stubGlobal("fetch", upstream)

    const request = new NextRequest("https://gravitre.app/api/voice/sessions", {
      method: "POST",
      headers: {
        authorization: "Bearer synthetic-tenant-a",
        "x-org-id": "tenant-a",
        "x-environment": "synthetic",
        cookie: "session=must-not-forward",
        "x-admin-override": "must-not-forward",
      },
      body: JSON.stringify({ message: "synthetic" }),
    })
    const response = await proxyVoiceJson(request, "/api/voice/sessions")
    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({
      org_id: "tenant-a", environment: "synthetic", status: "ok",
    })
    expect(upstream).toHaveBeenCalledTimes(1)
    const [url, init] = upstream.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${PRODUCTION_BACKEND_URL}/api/voice/sessions`)
    expect(init.cache).toBe("no-store")
    expect(init.method).toBe("POST")
    expect(init.body).toBe(JSON.stringify({ message: "synthetic" }))
    const sent = new Headers(init.headers)
    expect(sent.get("authorization")).toBe("Bearer synthetic-tenant-a")
    expect(sent.get("x-org-id")).toBe("tenant-a")
    expect(sent.get("x-environment")).toBe("synthetic")
    expect(sent.get("content-type")).toBe("application/json")
    expect(sent.has("cookie")).toBe(false)
    expect(sent.has("x-admin-override")).toBe(false)
  })

  it("preserves an upstream tenant-denial status without fabricating success", async () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = vi.fn(async () => Response.json(
      { detail: "Tenant access denied" }, { status: 403 },
    ))
    vi.stubGlobal("fetch", upstream)

    const request = new NextRequest("https://gravitre.app/api/voice/sessions", {
      method: "GET",
      headers: { authorization: "Bearer wrong-tenant", "x-org-id": "tenant-b" },
    })
    const response = await proxyVoiceJson(request, "/api/voice/sessions")
    expect(response.status).toBe(403)
    expect(await response.json()).toEqual({ detail: "Tenant access denied" })
    const [, init] = upstream.mock.calls[0] as unknown as [string, RequestInit]
    const sent = new Headers(init.headers)
    expect(sent.get("x-org-id")).toBe("tenant-b")
    expect(sent.has("x-environment")).toBe(false)
    expect(init.body).toBeUndefined()
    expect(init.cache).toBe("no-store")
  })
})

describe("QA00 upstream no-body status and failure propagation", () => {
  it.each([204, 205, 304])("preserves bodyless status %i without constructing an invalid response", async (status) => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = vi.fn(async () => new Response(null, { status }))
    vi.stubGlobal("fetch", upstream)
    const request = new NextRequest("https://gravitre.app/api/voice/status", {
      headers: { authorization: "Bearer qa-synthetic" },
    })

    const result = await proxyVoiceJson(request, "/api/voice/status")
    expect(result.status).toBe(status)
    expect(await result.text()).toBe("")
    expect(upstream).toHaveBeenCalledTimes(1)
  })

  it("preserves a 401 upstream rejection and does not invent authenticated results", async () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("FASTAPI_BASE_URL", "")
    const upstream = vi.fn(async () => new Response("Unauthorized", {
      status: 401, headers: { "content-type": "text/plain" },
    }))
    vi.stubGlobal("fetch", upstream)

    const result = await proxyVoiceJson(
      new NextRequest("https://gravitre.app/api/voice/status"),
      "/api/voice/status",
    )
    expect(result.status).toBe(401)
    expect(await result.text()).toBe("Unauthorized")
    expect(result.headers.get("content-type")).toBe("text/plain")
    const [, init] = upstream.mock.calls[0] as unknown as [string, RequestInit]
    expect(new Headers(init.headers).has("authorization")).toBe(false)
  })
})
