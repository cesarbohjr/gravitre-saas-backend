import { describe, expect, it } from "vitest"
import { isGravitreAIAllowed } from "@/components/gravitre/ai-auth-gate"
import { mayShowGravitreAIHelper, shouldShowGravitreAIHelper } from "@/components/gravitre/ai-helper"

const authed = { hasSession: true, loading: false }
const anon = { hasSession: false, loading: false }

describe("isGravitreAIAllowed", () => {
  it("allows a resolved session", () => {
    expect(isGravitreAIAllowed(authed)).toBe(true)
  })

  it("denies an anonymous visitor", () => {
    expect(isGravitreAIAllowed(anon)).toBe(false)
  })

  it("denies while the session is still resolving", () => {
    // The regression this pins: defaulting to allowed during `loading` is what
    // flashes authenticated UI at logged-out visitors on a cold load.
    expect(isGravitreAIAllowed({ hasSession: false, loading: true })).toBe(false)
  })

  it("denies during loading even when a stale user object is still present", () => {
    // Mid-logout the provider can briefly report both. Loading must win, or the
    // assistant stays on screen through the transition.
    expect(isGravitreAIAllowed({ hasSession: true, loading: true })).toBe(false)
  })
})

describe("mayShowGravitreAIHelper", () => {
  const base = {
    pathname: "/dashboard",
    hasSession: true,
    loading: false,
    floatEnabled: true,
    floatOpen: false,
  }

  it("shows the launcher to an authenticated operator", () => {
    expect(mayShowGravitreAIHelper(base)).toBe(true)
  })

  it("does not render the launcher without a session", () => {
    expect(mayShowGravitreAIHelper({ ...base, hasSession: false })).toBe(false)
  })

  it("does not render the launcher on the marketing homepage without a session", () => {
    // `shouldShowGravitreAIHelper("/")` is true by design, so before the auth
    // check existed the only thing keeping the launcher off `/` was a request
    // header. This asserts the path check alone is no longer load-bearing.
    expect(shouldShowGravitreAIHelper("/")).toBe(true)
    expect(mayShowGravitreAIHelper({ ...base, pathname: "/", hasSession: false })).toBe(false)
  })

  it("keeps the launcher for an authenticated operator on /", () => {
    expect(mayShowGravitreAIHelper({ ...base, pathname: "/" })).toBe(true)
  })

  it("does not render the launcher while the session resolves", () => {
    expect(mayShowGravitreAIHelper({ ...base, hasSession: false, loading: true })).toBe(false)
  })

  it("still suppresses the launcher on the full /ai surface", () => {
    expect(mayShowGravitreAIHelper({ ...base, pathname: "/ai" })).toBe(false)
    expect(mayShowGravitreAIHelper({ ...base, pathname: "/ai/threads/1" })).toBe(false)
  })

  it("still suppresses the launcher while the float workspace is open", () => {
    expect(mayShowGravitreAIHelper({ ...base, floatOpen: true })).toBe(false)
  })

  it("respects the feature flag being off", () => {
    expect(mayShowGravitreAIHelper({ ...base, floatEnabled: false })).toBe(false)
  })

  it("denies anonymous visitors on every route the launcher would otherwise take", () => {
    for (const pathname of ["/", "/pricing", "/dashboard", "/agents", "/settings/billing"]) {
      expect(mayShowGravitreAIHelper({ ...base, pathname, hasSession: false })).toBe(false)
    }
  })
})
