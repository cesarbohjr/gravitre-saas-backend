import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"

/**
 * createSupabaseRouteClient used the service role key whenever a request had no
 * Authorization header. Route handlers take the org id from the caller (?org_id=
 * or x-org-id), and /api/* skips the session check in proxy.ts, so an anonymous
 * request naming any org id ran with RLS bypassed. These tests pin that a route
 * client only ever carries the anon key, with or without the caller's token.
 */

const createClient = vi.fn((url: string, key: string, options: unknown) => ({ url, key, options }))

vi.mock("@supabase/supabase-js", () => ({
  createClient: (url: string, key: string, options: unknown) => createClient(url, key, options),
}))

vi.mock("@/lib/supabase/url", () => ({
  getSupabaseDataUrl: () => "https://project.supabase.co",
  getSupabaseServiceUrl: () => "https://project.supabase.co",
}))

const ANON = "anon-key"
const SERVICE = "service-role-key"

function request(headers: Record<string, string> = {}, query = "") {
  return new NextRequest(`https://gravitre.app/api/sessions${query}`, { headers })
}

describe("createSupabaseRouteClient", () => {
  const env = { ...process.env }

  beforeEach(() => {
    vi.resetModules()
    createClient.mockClear()
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = ANON
    process.env.SUPABASE_SERVICE_ROLE_KEY = SERVICE
    delete process.env.GRAVITRE_DEV_UNAUTHENTICATED_SERVICE_ROLE
  })

  afterEach(() => {
    process.env = { ...env }
  })

  it("never uses the service role for an anonymous request naming an org", async () => {
    const { createSupabaseRouteClient, getRouteClientAuthMode } = await import("@/lib/supabase/server")
    const req = request({ "x-org-id": "11111111-1111-4111-8111-111111111111" }, "?org_id=other-org")
    createSupabaseRouteClient(req)
    expect(createClient).toHaveBeenCalledTimes(1)
    expect(createClient.mock.calls[0][1]).toBe(ANON)
    expect(getRouteClientAuthMode(req)).toMatchObject({ usingServiceRole: false, usingAnonKey: true })
  })

  it("uses the anon key plus the caller's token when signed in", async () => {
    const { createSupabaseRouteClient } = await import("@/lib/supabase/server")
    createSupabaseRouteClient(request({ authorization: "Bearer user-jwt" }))
    const [, key, options] = createClient.mock.calls[0]
    expect(key).toBe(ANON)
    expect(options).toMatchObject({ global: { headers: { Authorization: "Bearer user-jwt" } } })
  })

  it("ignores the dev opt-in in production", async () => {
    process.env.GRAVITRE_DEV_UNAUTHENTICATED_SERVICE_ROLE = "1"
    vi.stubEnv("NODE_ENV", "production")
    const { createSupabaseRouteClient } = await import("@/lib/supabase/server")
    createSupabaseRouteClient(request())
    expect(createClient.mock.calls[0][1]).toBe(ANON)
    vi.unstubAllEnvs()
  })

  it("allows the old behaviour only with the explicit local dev opt-in", async () => {
    process.env.GRAVITRE_DEV_UNAUTHENTICATED_SERVICE_ROLE = "1"
    vi.stubEnv("NODE_ENV", "development")
    const { createSupabaseRouteClient } = await import("@/lib/supabase/server")
    createSupabaseRouteClient(request())
    expect(createClient.mock.calls[0][1]).toBe(SERVICE)
    vi.unstubAllEnvs()
  })
})
