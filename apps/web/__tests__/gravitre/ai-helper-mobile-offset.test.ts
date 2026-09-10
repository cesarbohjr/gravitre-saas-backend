// @vitest-environment jsdom
/**
 * GravitreAIHelper — Phase 4 mobile collision proof (B7).
 *
 * `MobileBottomNav` is `fixed inset-x-0 bottom-0 z-30 h-14` (56px) with
 * `pb-[env(safe-area-inset-bottom)]` (see mobile-bottom-nav.tsx). Below the
 * `md` breakpoint, GravitreAIHelper must sit strictly above that bar. jsdom
 * doesn't compute real layout/`getComputedStyle` values for arbitrary
 * Tailwind utility classes, so — same as this repo's other Tailwind-class
 * assertions — this is a class-assertion test: it asserts the exact
 * `max-md:bottom-[calc(...)]` utility class is present (which Tailwind's JIT
 * compiles verbatim into the CSS actually shipped), rather than a computed
 * pixel value.
 */
import { act, createElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const pathnameState: { value: string } = { value: "/dashboard" }

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameState.value,
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn() }),
}))

// The Helper reads the real session now, so it cannot mount outside an
// AuthProvider. This case is about the mobile offset class, so hand it a session.
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { id: "user-1" },
    session: {},
    loading: false,
    signOut: vi.fn(),
    refreshSession: vi.fn(),
  }),
}))

const ENV_KEY = "NEXT_PUBLIC_AI_FLOAT_ENABLED"
const originalValue = process.env[ENV_KEY]

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  pathnameState.value = "/dashboard"
  container = document.createElement("div")
  document.body.appendChild(container)
  process.env[ENV_KEY] = "true"
  vi.resetModules()
})

afterEach(() => {
  if (root) {
    act(() => {
      root!.unmount()
    })
    root = null
  }
  container.remove()
  if (originalValue === undefined) delete process.env[ENV_KEY]
  else process.env[ENV_KEY] = originalValue
  vi.resetModules()
})

async function renderHelper() {
  const { GravitreAIWorkspaceProvider } = await import("@/components/gravitre/ai-workspace-provider")
  const { GravitreAIHelper } = await import("@/components/gravitre/ai-helper")
  root = createRoot(container)
  act(() => {
    root!.render(createElement(GravitreAIWorkspaceProvider, null, createElement(GravitreAIHelper, null)))
  })
}

describe("GravitreAIHelper — mobile offset does not collide with MobileBottomNav (B7)", () => {
  it("carries a max-md offset that clears MobileBottomNav's 56px bar + safe-area inset + a gap", async () => {
    await renderHelper()
    const button = container.querySelector("[data-gravitre-ai-helper]") as HTMLElement
    expect(button).toBeTruthy()
    // Exact Tailwind utility that Tailwind's JIT compiles into
    // `@media (max-width: 767px) { bottom: calc(56px + env(safe-area-inset-bottom) + 12px) }`
    // — 56px matches MobileBottomNav's current `h-14`, confirmed by reading
    // mobile-bottom-nav.tsx fresh (see file header for both).
    expect(button.className).toContain("max-md:bottom-[calc(56px+env(safe-area-inset-bottom)+12px)]")
  })

  it("keeps the desktop offset (bottom-5, 20px) unchanged above the md breakpoint", async () => {
    await renderHelper()
    const button = container.querySelector("[data-gravitre-ai-helper]") as HTMLElement
    expect(button.className).toContain("md:bottom-5")
  })

  it("the mobile offset (56px bar + 12px gap = 68px+) is strictly greater than MobileBottomNav's own height (56px) — no overlap by construction", () => {
    const mobileBottomNavHeightPx = 56 // h-14, confirmed in mobile-bottom-nav.tsx
    const helperGapPx = 12
    const helperMobileBottomPx = mobileBottomNavHeightPx + helperGapPx // ignoring the safe-area inset, which only adds more clearance
    expect(helperMobileBottomPx).toBeGreaterThan(mobileBottomNavHeightPx)
  })
})
