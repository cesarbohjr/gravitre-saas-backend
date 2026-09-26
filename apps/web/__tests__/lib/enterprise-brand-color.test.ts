import { describe, expect, it, vi } from "vitest"

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: null }) }))

import { brandColorCss, brandColorReadableOnDark } from "@/lib/enterprise-branding-context"

describe("enterprise brand color theming", () => {
  it("applies a dark brand color in light mode only, keeping the dark theme primary readable", () => {
    const css = brandColorCss("#0f172a")
    expect(css).toContain(":root:not(.dark) { --primary: #0f172a;")
    expect(css).not.toContain(".dark {")
    expect(brandColorReadableOnDark("#0f172a")).toBe(false)
  })

  it("applies a light-enough brand color in both themes", () => {
    const css = brandColorCss("#16a374")
    expect(brandColorReadableOnDark("#16a374")).toBe(true)
    expect(css).toContain(":root:not(.dark) { --primary: #16a374;")
    expect(css).toContain(".dark { --primary: #16a374;")
  })

  it("emits nothing without a valid brand color", () => {
    expect(brandColorCss(null)).toBeNull()
    expect(brandColorCss("not-a-color")).toBeNull()
  })
})
