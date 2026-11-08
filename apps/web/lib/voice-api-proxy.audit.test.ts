import { afterEach, describe, expect, it, vi } from "vitest"
import { forwardAuthHeaders, voiceFastApiBase } from "@/lib/voice-api-proxy"
import { NextRequest } from "next/server"
import { PRODUCTION_BACKEND_URL } from "@/lib/public-urls"

afterEach(() => {
  vi.unstubAllEnvs()
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
