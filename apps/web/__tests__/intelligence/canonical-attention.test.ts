import { describe, expect, it } from "vitest"
import {
  canonicalLearningsForDisplay,
  canonicalPredictionsToAttentionSignals,
} from "@/lib/intelligence/canonical-attention"

describe("canonicalPredictionsToAttentionSignals", () => {
  it("uses businessStatement as title and ranks by confidence", () => {
    const rows = canonicalPredictionsToAttentionSignals([
      { id: "p1", businessStatement: "Low priority", confidence: 0.3 },
      { id: "p2", businessStatement: "OAuth expiring", confidence: 0.9, department: "sales" },
    ])
    expect(rows[0].title).toBe("OAuth expiring")
    expect(rows[0].id).toBe("p2")
    expect(rows[0].source).toBe("canonical_prediction")
  })
})

describe("canonicalLearningsForDisplay", () => {
  it("returns business statements only", () => {
    const rows = canonicalLearningsForDisplay([
      { id: "l1", businessStatement: "Enterprise deals close faster with multi-threading" },
    ])
    expect(rows[0].statement).toContain("Enterprise deals")
  })
})
