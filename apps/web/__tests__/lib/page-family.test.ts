import { describe, expect, it } from "vitest"
import { familyHidesTopBar, isAiHelpRoute, resolvePageFamily } from "@/lib/page-family"

describe("page families (G-STRUCT A1)", () => {
  it("resolves operating surfaces", () => {
    for (const path of [
      "/home",
      "/dashboard",
      "/agents",
      "/workflows",
      "/assignments",
      "/approvals",
      "/goals",
      "/schedules",
      "/activity",
      "/sources",
    ]) {
      expect(resolvePageFamily(path), path).toBe("operating")
    }
  })

  it("keeps a single source's schema/evidence view in the expert family", () => {
    expect(resolvePageFamily("/sources/s1")).toBe("expert")
  })

  it("resolves expert surfaces, including agent config but not agent creation", () => {
    expect(resolvePageFamily("/intelligence")).toBe("expert")
    expect(resolvePageFamily("/intelligence/model-studio")).toBe("expert")
    expect(resolvePageFamily("/agents/a1")).toBe("expert")
    expect(resolvePageFamily("/agents/new")).toBe("standard")
  })

  it("resolves immersive surfaces and only the builder hides the top bar", () => {
    expect(resolvePageFamily("/ai")).toBe("immersive")
    expect(resolvePageFamily("/workflows/w1/builder")).toBe("immersive")
    expect(resolvePageFamily("/agents/a1/chat")).toBe("immersive")
    expect(familyHidesTopBar("/workflows/w1/builder")).toBe(true)
    expect(familyHidesTopBar("/ai")).toBe(false)
  })

  it("falls back to standard", () => {
    expect(resolvePageFamily("/marketplace/assets")).toBe("standard")
    expect(resolvePageFamily("/settings")).toBe("standard")
  })

  it("keeps chat help documents scrollable without changing conversation routes", () => {
    for (const path of ["/ai/help/context", "/ai/help/control", "/ai/help/context?from=chat"]) {
      expect(isAiHelpRoute(path)).toBe(true)
      expect(resolvePageFamily(path)).toBe("standard")
    }
    expect(isAiHelpRoute("/ai/helpful")).toBe(false)
    expect(resolvePageFamily("/ai")).toBe("immersive")
  })
})
