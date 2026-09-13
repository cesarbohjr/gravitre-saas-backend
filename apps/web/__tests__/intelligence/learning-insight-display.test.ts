import { describe, expect, it } from "vitest"
import { formatLearningInsightRow, formatLearningInsights } from "@/lib/intelligence/learning-insight-display"

describe("formatLearningInsights", () => {
  it("maps canonical learning fields for customer display", () => {
    const [insight] = formatLearningInsights([
      {
        id: "l1",
        businessStatement: "Enterprise deals close faster with multi-threading",
        learnedFrom: ["memory_promotion"],
        evidence: ["3 won deals in Q3"],
        affectedEntities: ["Enterprise segment"],
        source: { system: "memory_promotion", recordId: "l1" },
        learnedAt: "2026-09-01T12:00:00Z",
      },
    ])
    expect(insight.statement).toContain("Enterprise deals")
    expect(insight.learnedFrom).toEqual(["memory_promotion"])
    expect(insight.evidence).toEqual(["3 won deals in Q3"])
    expect(insight.provenance).toContain("memory_promotion")
    expect(insight.learnedAtLabel).toBeTruthy()
  })

  it("handles sparse rows without inventing evidence", () => {
    const insight = formatLearningInsightRow({ businessStatement: "Pattern noted" })
    expect(insight.evidence).toEqual([])
    expect(insight.statement).toBe("Pattern noted")
  })
})
