import { describe, expect, it, beforeEach, afterEach, vi } from "vitest"

describe("getSupabasePublicUrl", () => {
  const env = process.env

  beforeEach(() => {
    vi.unstubAllEnvs()
    process.env = { ...env }
    delete process.env.NEXT_PUBLIC_SUPABASE_AUTH_URL
    delete process.env.NEXT_PUBLIC_SUPABASE_URL
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    process.env = env
  })

  it("prefers NEXT_PUBLIC_SUPABASE_AUTH_URL over project URL", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_AUTH_URL = "https://auth.gravitre.app"
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://abc.supabase.co"
    const { getSupabasePublicUrl } = await import("@/lib/supabase/url")
    expect(getSupabasePublicUrl()).toBe("https://auth.gravitre.app")
  })

  it("uses gravitre.app in production when no branded env is set", async () => {
    vi.stubEnv("NODE_ENV", "production")
    process.env.NEXT_PUBLIC_APP_URL = "https://gravitre.app"
    const { getSupabasePublicUrl } = await import("@/lib/supabase/url")
    expect(getSupabasePublicUrl()).toBe("https://gravitre.app")
  })

  it("sanitizes supabase.co from error messages", async () => {
    const { sanitizeAuthErrorMessage } = await import("@/lib/supabase/url")
    expect(sanitizeAuthErrorMessage("redirect to abc.supabase.co failed")).toBe(
      "redirect to gravitre.app failed",
    )
  })

  it("keeps server data-plane URL on the project host (not branded public origin)", async () => {
    vi.stubEnv("NODE_ENV", "production")
    process.env.NEXT_PUBLIC_APP_URL = "https://gravitre.app"
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://abc.supabase.co"
    const { getSupabasePublicUrl, getSupabaseDataUrl } = await import("@/lib/supabase/url")
    expect(getSupabasePublicUrl()).toBe("https://gravitre.app")
    expect(getSupabaseDataUrl()).toBe("https://abc.supabase.co")
  })

  it("server auth talks to the project host but keeps the browser cookie name", async () => {
    vi.stubEnv("NODE_ENV", "production")
    process.env.NEXT_PUBLIC_APP_URL = "https://gravitre.app"
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://abc.supabase.co"
    const { getSupabaseServerAuthConfig } = await import("@/lib/supabase/url")
    expect(getSupabaseServerAuthConfig()).toEqual({
      url: "https://abc.supabase.co",
      cookieName: "sb-gravitre-auth-token",
    })
  })

  it("server auth falls back to the public URL when no project host is known", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://localhost:54321"
    delete process.env.SUPABASE_URL
    delete process.env.SUPABASE_PROJECT_URL
    const { getSupabaseServerAuthConfig } = await import("@/lib/supabase/url")
    expect(getSupabaseServerAuthConfig()).toEqual({ url: "http://localhost:54321", cookieName: undefined })
  })
})
