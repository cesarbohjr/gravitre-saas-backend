import { describe, expect, it } from "vitest"
import { APP_ROUTES, LEGACY_APP_ROUTES } from "@/lib/app-routes"

describe("APP_ROUTES", () => {
  it("uses /search as canonical universal search", () => {
    expect(APP_ROUTES.universalSearch).toBe("/search")
  })

  it("uses /ai as canonical workspace surface", () => {
    expect(APP_ROUTES.gravitreAi).toBe("/ai")
    expect(APP_ROUTES.gravitreAiChat).toBe("/ai?mode=chat")
  })

  it("does not expose legacy paths in canonical routes", () => {
    const canonicalValues = Object.values(APP_ROUTES)
    expect(canonicalValues).not.toContain("/operator")
    expect(canonicalValues).not.toContain("/assistant")
    expect(canonicalValues).not.toContain("/tasks")
    expect(canonicalValues).not.toContain("/systems")
  })
})

describe("LEGACY_APP_ROUTES", () => {
  it("retains redirect-only legacy paths", () => {
    expect(LEGACY_APP_ROUTES.operator).toBe("/operator")
    expect(LEGACY_APP_ROUTES.assistant).toBe("/assistant")
    expect(LEGACY_APP_ROUTES.tasks).toBe("/tasks")
    expect(LEGACY_APP_ROUTES.systems).toBe("/systems")
  })
})
