import { describe, expect, it } from "vitest"
import { shouldMountAppShell } from "@/lib/app-shell-paths"

describe("shouldMountAppShell", () => {
  it("excludes marketing and auth surfaces", () => {
    expect(shouldMountAppShell("/")).toBe(false)
    expect(shouldMountAppShell("/login")).toBe(false)
    expect(shouldMountAppShell("/pricing")).toBe(false)
    expect(shouldMountAppShell("/terms")).toBe(false)
    expect(shouldMountAppShell("/privacy")).toBe(false)
    expect(shouldMountAppShell("/welcome")).toBe(false)
    expect(shouldMountAppShell("/lite/deliverables")).toBe(false)
    expect(shouldMountAppShell("/auth/callback")).toBe(false)
    expect(shouldMountAppShell("/settings/organizations")).toBe(false)
  })

  it("includes authenticated app surfaces", () => {
    expect(shouldMountAppShell("/home")).toBe(true)
    expect(shouldMountAppShell("/agents")).toBe(true)
    expect(shouldMountAppShell("/agents/abc")).toBe(true)
    expect(shouldMountAppShell("/settings")).toBe(true)
    expect(shouldMountAppShell("/settings/billing")).toBe(true)
    expect(shouldMountAppShell("/intelligence/predictive")).toBe(true)
  })
})
