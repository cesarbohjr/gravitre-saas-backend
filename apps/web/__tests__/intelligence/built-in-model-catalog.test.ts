import { describe, expect, it } from "vitest"
import {
  BUILT_IN_MODEL_GUIDES,
  getBuiltInModelGuide,
  groupBuiltInModels,
  statusLabel,
  statusShortLabel,
  summarizeBrainHealth,
  type BuiltInModelListItem,
} from "@/lib/built-in-model-catalog"

function item(
  id: string,
  status: string,
  sufficiency: BuiltInModelListItem["sufficiency"],
): BuiltInModelListItem {
  return {
    id,
    status,
    useCases: [],
    sufficiency,
    outcomeScore: null,
    lastTrained: "—",
    guide: getBuiltInModelGuide(id),
  }
}

describe("built-in-model-catalog", () => {
  it("exposes novice labels for catalog keys shown in the screenshot", () => {
    expect(BUILT_IN_MODEL_GUIDES.churn_risk_scorer.label).toBe("Customer churn risk")
    expect(BUILT_IN_MODEL_GUIDES.active_learning.whyItMatters.length).toBeGreaterThan(20)
    expect(getBuiltInModelGuide("unknown_model_xyz").label).toContain("Unknown")
  })

  it("groups models by business domain", () => {
    const groups = groupBuiltInModels([
      item("churn_risk_scorer", "trained", { value: 100, label: "40 / 30", available: 40, required: 30 }),
      item("intent_classifier", "heuristic", { value: 40, label: "20 / 50", available: 20, required: 50 }),
      item("diffusion_model", "planned", { value: null, label: "Not trainable yet", available: 0, required: 0 }),
    ])
    const titles = groups.map((g) => g.domain.title)
    expect(titles).toContain("Customers & deals")
    expect(titles).toContain("Learning engine")
    expect(titles).toContain("Coming capabilities")
  })

  it("summarizes brain health without treating the gate as a max", () => {
    const health = summarizeBrainHealth([
      item("churn_risk_scorer", "trained", { value: 100, label: "40 / 30", available: 40, required: 30 }),
      item("intent_classifier", "heuristic", { value: 40, label: "20 / 50", available: 20, required: 50 }),
      item("diffusion_model", "planned", { value: null, label: "n/a", available: 0, required: 0 }),
    ])
    expect(health.trained).toBe(1)
    expect(health.learning).toBe(1)
    expect(health.collecting).toBe(1)
    expect(health.planned).toBe(1)
    expect(health.readyPct).toBe(50)
    expect(statusLabel("trained")).toMatch(/Trained/i)
    expect(statusShortLabel("heuristic")).toBe("Learning")
    expect(statusShortLabel("planned")).toBe("Roadmap")
  })
})
