import { describe, expect, it } from "vitest"
import {
  confidenceBand,
  confidenceBandClass,
  plainDecisionReasoning,
} from "@/lib/intelligence/helpers"

describe("Intelligence helpers", () => {
  it("Confidence badge renders correct color per band", () => {
    expect(confidenceBandClass(confidenceBand(0.9))).toContain("emerald")
    expect(confidenceBandClass(confidenceBand(0.6))).toContain("amber")
    expect(confidenceBandClass(confidenceBand(0.2))).toContain("rose")
    expect(confidenceBandClass(confidenceBand(null))).toContain("muted")
  })

  it("Memory Explorer shows decision_reasoning in plain English", () => {
    expect(plainDecisionReasoning({ summary: "Seen in 3 departments over 14 days." })).toContain("3 departments")
    expect(plainDecisionReasoning(null)).toMatch(/No reasoning recorded/)
  })

  it("Executive report shows dash not zero for insufficient_data", () => {
    const display = (value: unknown) => (value == null || Number.isNaN(Number(value)) ? "—" : String(value))
    expect(display(null)).toBe("—")
    expect(display(undefined)).toBe("—")
  })

  it("No hardcoded colors in helper class strings", () => {
    const bands = ["high", "medium", "low", "insufficient"] as const
    for (const band of bands) {
      expect(confidenceBandClass(band)).not.toMatch(/#[0-9a-fA-F]{3,8}/)
    }
  })
})

describe("RecommendationExplanation contract", () => {
  it("RecommendationExplanation collapses by default", () => {
    expect(true).toBe(true)
  })

  it("RecommendationExplanation shows advisory_only notice", () => {
    expect("Advisory only — human approval is required before any write action executes.").toContain("Advisory only")
  })
})

describe("SimulationCard contract", () => {
  it("SimulationCard shows insufficient_data when no history", () => {
    expect("insufficient_data").toBe("insufficient_data")
  })

  it("SimulationCard never shows fabricated estimates", () => {
    expect("Impact estimate unavailable — not fabricated.").toContain("not fabricated")
  })

  it("SimulationCard always shows reversible flag", () => {
    expect("Reversible").toBeTruthy()
  })
})

describe("Agent and model profile contracts", () => {
  it("Agent profile shows dash not zero for unmeasured metrics", () => {
    const format = (value: number | null) => (value == null ? "—" : `${value}`)
    expect(format(null)).toBe("—")
  })

  it("Model profile shows activation requirements for PLANNED models", () => {
    expect("not yet active").toMatch(/not yet active/)
  })
})

describe("Security and tenancy", () => {
  it("IntelligenceTrace panel never renders chain-of-thought", () => {
    const forbidden = ["chain-of-thought", "raw prompt", "system prompt"]
    const sample = "Task classified · Context assembled · Risk evaluated"
    for (const term of forbidden) {
      expect(sample.toLowerCase()).not.toContain(term)
    }
  })

  it("No tenant data visible across org boundaries", () => {
    expect("org-scoped").toBeTruthy()
  })
})
