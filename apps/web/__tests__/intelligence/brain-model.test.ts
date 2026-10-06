import { describe, expect, it } from "vitest"
import type { IntelligencePageContextResponse } from "@/lib/api"
import { buildBrainModel, buildExampleBrainModel, nodesForCount } from "@/lib/intelligence/brain-model"

const metrics = (over: Partial<IntelligencePageContextResponse["metrics"]> = {}) => ({
  knowledge: {},
  learning: {},
  predictions: {},
  execution: {},
  outcomes: {},
  ...over,
})

function context(snapshot: Partial<IntelligencePageContextResponse["snapshot"]>, m = metrics()) {
  return {
    snapshot: {
      generatedAt: "2026-10-06T12:00:00Z",
      tenantId: "t",
      timeWindowHours: 24,
      coreState: "active",
      agents: [],
      predictions: [],
      learnings: [],
      metrics: m,
      qualityFlags: [],
      departments: [],
      ...snapshot,
    },
    graph: { nodes: [], edges: [] },
    activeLens: "knows",
    availableLenses: [],
    metrics: m,
    qualityFlags: [],
    suggestedQuestions: [],
  } as IntelligencePageContextResponse
}

describe("buildBrainModel", () => {
  it("shows unknown as a dash, never zero", () => {
    const model = buildBrainModel(null)
    expect(model.layers.map((l) => l.count)).toEqual([null, null, null, null, null])
    expect(model.metrics.find((m) => m.id === "forecast-confidence")?.value).toBe("—")
    expect(model.metrics.find((m) => m.id === "agents")?.value).toBe("—")
    expect(model.example).toBe(false)
  })

  it("maps canonical metrics onto the five layers", () => {
    const model = buildBrainModel(
      context(
        { knowledgeEntityTypes: ["agent", "account"] },
        metrics({
          knowledge: { knownEntities: 40, knownRelationships: 12 },
          learning: { recentLearnings: 3, modelsTracked: 2 },
          predictions: { activePredictions: 5 },
        }),
      ),
    )
    expect(model.layers.map((l) => [l.id, l.count])).toEqual([
      ["sources", 2],
      ["knowledge", 40],
      ["learning", 3],
      ["models", 2],
      ["forecasts", 5],
    ])
    expect(model.layers[1].detail).toBe("40 entities · 12 links")
  })

  it("ranks forecasts by confidence and accepts percentages", () => {
    const model = buildBrainModel(
      context({
        predictions: [
          { id: "a", businessStatement: "Low", confidence: 0.4 },
          { id: "b", businessStatement: "High", confidence: 91 },
          { id: "c", businessStatement: "Unscored" },
        ],
      }),
    )
    expect(model.confidence.map((c) => c.id)).toEqual(["b", "a"])
    expect(model.confidence[0].confidence).toBeCloseTo(0.91)
    expect(model.metrics.find((m) => m.id === "forecast-confidence")?.value).toBe("65.5%")
  })

  it("builds the outcome curve and log from real outcomes, newest log first", () => {
    const model = buildBrainModel(
      context({
        outcomes: [
          { id: "o2", event: "deal_won", confidence: 0.8, createdAt: "2026-10-06T10:00:00Z" },
          { id: "o1", event: "lead_routed", confidence: 0.6, createdAt: "2026-10-06T08:00:00Z" },
          { id: "o3", event: "no_score", createdAt: "2026-10-06T11:00:00Z" },
        ],
      }),
    )
    expect(model.curve.map((p) => p.value)).toEqual([0.6, 0.8])
    expect(model.log[0]).toMatchObject({ tag: "OUTCOME", message: "no score" })
    expect(model.sparse).toBe(false)
  })

  it("flags an org with nothing learned, forecast, or measured as sparse", () => {
    expect(buildBrainModel(context({})).sparse).toBe(true)
  })
})

describe("example data", () => {
  it("is always marked as example", () => {
    const model = buildExampleBrainModel(Date.parse("2026-10-06T12:00:00Z"))
    expect(model.example).toBe(true)
    expect(model.curve.length).toBeGreaterThan(2)
  })
})

describe("nodesForCount", () => {
  it("keeps every layer between 3 and 12 nodes", () => {
    expect(nodesForCount(null)).toBe(3)
    expect(nodesForCount(0)).toBe(3)
    expect(nodesForCount(1_000_000)).toBe(12)
  })
})
