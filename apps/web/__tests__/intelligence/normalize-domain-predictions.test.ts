import { normalizeDomainPredictions } from "@/lib/intelligence/normalize-domain-predictions"

describe("normalizeDomainPredictions", () => {
  it("maps model→payload dict into card rows", () => {
    const rows = normalizeDomainPredictions({
      churn_risk_scorer: { status: "ok", risk_score: 0.8, advisory_only: true },
      sla_breach_predictor: { status: "insufficient_data" },
    })
    expect(rows).toHaveLength(2)
    expect(rows[0].model).toBe("churn_risk_scorer")
    expect(rows[0].risk_score).toBe(0.8)
    expect(rows[1].model).toBe("sla_breach_predictor")
  })

  it("passes through arrays", () => {
    const rows = normalizeDomainPredictions([{ model: "x", status: "ok" }])
    expect(rows).toEqual([{ model: "x", status: "ok" }])
  })

  it("returns empty for nullish", () => {
    expect(normalizeDomainPredictions(null)).toEqual([])
    expect(normalizeDomainPredictions(undefined)).toEqual([])
  })
})
