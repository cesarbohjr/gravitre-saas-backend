// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const auth = vi.hoisted(() => ({
  getUser: vi.fn(),
  getSession: vi.fn(),
}))

vi.mock("@/lib/supabaseClient", () => ({
  hasSupabasePublicEnv: true,
  supabaseClient: { auth },
}))

type ShotWindow = Window & { __GRAVITRE_AI_INSTRUMENT?: boolean }

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "development")
  vi.stubEnv("NEXT_PUBLIC_PLAYWRIGHT_E2E", "")
  window.history.replaceState(null, "", "/e2e/shots/marketplace")
  ;(window as ShotWindow).__GRAVITRE_AI_INSTRUMENT = true
  auth.getUser.mockResolvedValue({ data: { user: { id: "real-user" } }, error: null })
  auth.getSession.mockResolvedValue({ data: { session: { access_token: "real-token" } }, error: null })
})

afterEach(() => {
  delete (window as ShotWindow).__GRAVITRE_AI_INSTRUMENT
  vi.unstubAllEnvs()
  vi.clearAllMocks()
})

describe("screenshot access-token isolation", () => {
  it("allows the explicitly instrumented local shot route", async () => {
    const { getAccessToken } = await import("@/lib/auth-context")
    expect(await getAccessToken()).toBe("shot-access-token")
    expect(auth.getUser).not.toHaveBeenCalled()
  })

  it("never substitutes fixture auth in a normal production build", async () => {
    vi.stubEnv("NODE_ENV", "production")
    const { getAccessToken } = await import("@/lib/auth-context")
    expect(await getAccessToken()).toBe("real-token")
    expect(auth.getUser).toHaveBeenCalled()
  })

  it("does not treat instrumentation as a real signed-in user", async () => {
    vi.stubEnv("NODE_ENV", "production")
    auth.getUser.mockResolvedValue({ data: { user: null }, error: null })
    const { getAccessToken } = await import("@/lib/auth-context")
    expect(await getAccessToken()).toBeNull()
    expect(auth.getSession).not.toHaveBeenCalled()
  })

  it.each(["/marketplace/assets", "/agents", "/e2e/shots-not-a-route"])(
    "validates real auth outside the shot route: %s",
    async (path) => {
      window.history.replaceState(null, "", path)
      const { getAccessToken } = await import("@/lib/auth-context")
      expect(await getAccessToken()).toBe("real-token")
      expect(auth.getUser).toHaveBeenCalled()
    },
  )

  it("requires instrumentation even on an allowed shot route", async () => {
    delete (window as ShotWindow).__GRAVITRE_AI_INSTRUMENT
    const { getAccessToken } = await import("@/lib/auth-context")
    expect(await getAccessToken()).toBe("real-token")
  })

  it("supports an explicitly enabled production E2E build only on shots", async () => {
    vi.stubEnv("NODE_ENV", "production")
    vi.stubEnv("NEXT_PUBLIC_PLAYWRIGHT_E2E", "1")
    const { getAccessToken } = await import("@/lib/auth-context")
    expect(await getAccessToken()).toBe("shot-access-token")
    window.history.replaceState(null, "", "/agents")
    expect(await getAccessToken()).toBe("real-token")
  })
})
