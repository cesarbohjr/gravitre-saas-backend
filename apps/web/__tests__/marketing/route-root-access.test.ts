import { describe, expect, it } from "vitest"
import { classifyTopLevelRoute } from "@/lib/route-root-access"

describe("route classification and crawlable missing paths", () => {
  it("does not accidentally make application routes public", () => {
    for (const path of ["/ai", "/home", "/agents/123", "/settings/billing", "/marketplace/assets", "/onboarding"]) {
      expect(classifyTopLevelRoute(path)).toBe("private")
    }
  })
  it("recognizes marketing pages and their article URLs", () => {
    for (const path of ["/", "/about", "/pricing", "/blog/example", "/docs/guide", "/features/technology"]) {
      expect(classifyTopLevelRoute(path)).toBe("marketing")
    }
  })
  it("lets the Next router resolve unknown URLs as 404", () => {
    for (const path of ["/clearly-missing-seo-audit-xyz", "/llms.txt", "/nonsense/something"]) {
      expect(classifyTopLevelRoute(path)).toBe("unknown")
    }
  })
})
