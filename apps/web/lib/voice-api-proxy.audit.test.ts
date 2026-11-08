import { afterEach, describe, expect, it, vi } from "vitest"
import { voiceFastApiBase } from "@/lib/voice-api-proxy"
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
