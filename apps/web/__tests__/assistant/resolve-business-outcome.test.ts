import { describe, expect, it } from "vitest"
import { resolveBusinessOutcome } from "@/components/gravitre/assistant/chat-execution-panel"

describe("resolveBusinessOutcome", () => {
  it("prefers business_outcome with projection for chat evidence card", () => {
    const dto = resolveBusinessOutcome({
      success: true,
      business_outcome: {
        id: "bo-1",
        projection: "business_outcome",
        title: "Create list",
        sections: {
          summary: "Created list",
          evidence: {
            links: [{ label: "Vendor", href: "https://example.com", kind: "vendor" }],
          },
          verification: { verified: true, method: "module_a_verified_output" },
        },
      },
    })
    expect(dto?.id).toBe("bo-1")
    expect(dto?.projection).toBe("business_outcome")
    expect(dto?.sections?.evidence?.links?.[0]?.href).toContain("example.com")
  })

  it("returns null when no BusinessOutcome is present (legacy artifact path)", () => {
    expect(
      resolveBusinessOutcome({
        success: true,
        title: "Done",
        body: "No BO",
      }),
    ).toBeNull()
  })
})
