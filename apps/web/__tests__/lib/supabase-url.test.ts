import { describe, expect, it, beforeEach, afterEach } from "vitest"

describe("getSupabasePublicUrl", () => {
  const env = process.env

  beforeEach(() => {
    process.env = { ...env }
    delete process.env.NEXT_PUBLIC_SUPABASE_AUTH_URL
    delete process.env.NEXT_PUBLIC_SUPABASE_URL
    delete process.env.NODE_ENV
  })

  afterEach(() => {
    process.env = env
  })

  it("prefers NEXT_PUBLIC_SUPABASE_AUTH_URL over project URL", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_AUTH_URL = "https://auth.gravitre.app"
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://abc.supabase.co"
    const { getSupabasePublicUrl } = await import("@/lib/supabase/url")
    expect(getSupabasePublicUrl()).toBe("https://auth.gravitre.app")
  })

  it("uses gravitre.app in production when no branded env is set", async () => {
    process.env.NODE_ENV = "production"
    process.env.NEXT_PUBLIC_APP_URL = "https://gravitre.app"
    const { getSupabasePublicUrl } = await import("@/lib/supabase/url")
    expect(getSupabasePublicUrl()).toBe("https://auth.gravitre.app")
  })

  it("sanitizes supabase.co from error messages", async () => {
    const { sanitizeAuthErrorMessage } = await import("@/lib/supabase/url")
    expect(sanitizeAuthErrorMessage("redirect to abc.supabase.co failed")).toBe(
      "redirect to gravitre.app failed",
    )
  })
})
