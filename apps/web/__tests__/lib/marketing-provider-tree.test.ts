import { describe, expect, it } from "vitest"
import {
  isMarketingContentRoute,
  usesMarketingProviderTree,
} from "@/lib/is-marketing-route"

/**
 * `usesMarketingProviderTree` decides two things that must agree exactly: which
 * paths proxy.ts marks with `x-gravitre-marketing`, and which paths
 * MarketingProviders considers legitimate. A path that returns false while being
 * served the marketing tree crashes; a path that returns true while needing the
 * operator tree would reload forever.
 */
describe("usesMarketingProviderTree", () => {
  it.each([
    "/",
    "/pricing",
    "/login",
    "/get-started",
    "/about",
    "/privacy",
    "/terms",
    "/security",
    "/forgot-password",
    "/features/voice",
    "/docs",
    "/docs/getting-started",
    "/blog/some-post",
  ])("serves %s with the marketing tree", (pathname) => {
    expect(usesMarketingProviderTree(pathname)).toBe(true)
  })

  it.each(["/deck", "/deck/2", "/deck/intro/slide"])(
    "keeps the unlisted deck surface on the marketing tree (%s)",
    (pathname) => {
      // Regression guard: /deck is intentionally absent from
      // isMarketingContentRoute so it stays out of the sitemap. If the shared
      // predicate missed it, the guard would reload /deck endlessly.
      expect(isMarketingContentRoute(pathname)).toBe(false)
      expect(usesMarketingProviderTree(pathname)).toBe(true)
    },
  )

  it.each([
    "/ai",
    "/home",
    "/agents",
    "/workflows",
    "/connectors",
    "/approvals",
    "/settings",
    "/settings/billing",
    "/welcome",
    "/marketplace",
    "/activity",
  ])("requires the operator tree for %s", (pathname) => {
    expect(usesMarketingProviderTree(pathname)).toBe(false)
  })

  it("does not treat backend api routes as marketing", () => {
    expect(usesMarketingProviderTree("/api/chat")).toBe(false)
  })

  it("keeps the marketing /api content page on the marketing tree", () => {
    expect(usesMarketingProviderTree("/api")).toBe(true)
  })

  it("does not confuse a prefix with a longer sibling segment", () => {
    // /docs matches, but /docsomething is a different route.
    expect(usesMarketingProviderTree("/docsomething")).toBe(false)
  })

  it("treats an empty pathname as non-marketing without throwing", () => {
    expect(usesMarketingProviderTree("")).toBe(false)
  })
})
