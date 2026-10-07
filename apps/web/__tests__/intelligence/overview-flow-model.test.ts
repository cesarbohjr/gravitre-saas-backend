import { describe, expect, it } from "vitest"
import type { IntelligencePageContextResponse } from "@/lib/api"
import { buildLiveFlowModel } from "@/components/intelligence/overview/flow-model"
import { buildExampleFlowModel } from "@/components/intelligence/overview/example-flow"

const now = new Date().toISOString()

function ctx(overrides: Partial<IntelligencePageContextResponse["snapshot"]> = {}): IntelligencePageContextResponse {
  const metrics = {
    knowledge: { knownEntities: 42, knownRelationships: 18 },
    learning: { relationshipsLearned: 18, modelsTracked: 1 },
    predictions: {},
    execution: {},
    outcomes: { outcomeEventsInWindow: overrides.outcomes?.length ?? 0 },
  }
  return {
    snapshot: {
      generatedAt: now,
      tenantId: "org",
      timeWindowHours: 24,
      coreState: "flow-inward",
      agents: [],
      predictions: [],
      learnings: [],
      models: [],
      knowledgeEntityTypes: ["deal"],
      metrics,
      qualityFlags: [],
      departments: [],
      outcomes: [],
      ...overrides,
    },
    graph: { nodes: [], edges: [] },
    activeLens: "knows",
    availableLenses: [],
    metrics,
    qualityFlags: [],
    suggestedQuestions: [],
  }
}

describe("overview flow model (live)", () => {
  it("shows dashes and placeholders, never zeros, before data loads", () => {
    const model = buildLiveFlowModel({ pageContext: null, loading: true })
    expect(model.example).toBe(false)
    expect(model.stats.signalsToday).toBeNull()
    expect(model.stats.connections).toBeNull()
    expect(model.stats.outcomesFed).toBeNull()
    expect(model.events).toEqual([])
    expect(model.quiet).toBeNull()
    for (const layer of ["knowledge", "learning", "models", "forecasts"]) {
      expect(model.nodes.some((n) => n.layer === layer && n.placeholder)).toBe(true)
    }
  })

  it("builds nodes, links and activity from real records", () => {
    const model = buildLiveFlowModel({
      pageContext: ctx({
        outcomes: [{ id: "o1", event: "workflow_executed", entityType: "deal", department: "sales", createdAt: now }],
        models: [{ id: "churn_risk", businessLabel: "Churn risk", status: "collecting" }],
        predictions: [{ id: "p1", subject: "Renewals at risk", businessStatement: "Renewals at risk", sourceModel: "churn_risk" }],
      }),
      connectors: [{ id: "c1", name: "HubSpot", vendor: "hubspot", status: "active", last_sync_at: now }],
      candidates: [{ id: "m1", content: "Deals with a technical call close faster", status: "pending_approval", frequency: 7 }],
      attribution: { minSampleSize: 15, agentSummaries: [{ sampleSize: 4, sufficientData: false }] },
    })
    const ids = model.nodes.map((n) => n.id)
    expect(ids).toEqual(expect.arrayContaining(["src:c1", "src:platform", "kn:deal", "lr:m1", "md:churn_risk", "fc:p1"]))
    expect(model.edges.find((e) => e.key === "src:platform>kn:deal")?.evidence).toBe(true)
    expect(model.edges.find((e) => e.key === "md:churn_risk>fc:p1")?.evidence).toBe(true)
    expect(model.nodes.find((n) => n.id === "fc:p1")?.scored).toBe(false)
    expect(model.events[0].text).toBe("A workflow ran in sales")
    expect(model.events[0].path).toEqual(["src:platform", "kn:deal"])
    expect(model.learnings[0]).toMatchObject({ reinforced: 7, confidence: null })
    expect(model.stats).toMatchObject({ signalsToday: 1, outcomesFed: 4, outcomesTarget: 15, forecastValue: "Calibrating" })
    expect(model.stats.forecastNote).toBe("11 outcomes until scoring starts")
    expect(model.quiet).toBeNull()
  })

  it("says the core is quiet when nothing reached it in the window", () => {
    const old = new Date(Date.now() - 10 * 86_400_000).toISOString()
    const model = buildLiveFlowModel({
      pageContext: ctx(),
      connectors: [{ id: "c1", name: "HubSpot", vendor: "hubspot", status: "active", last_sync_at: old }],
    })
    expect(model.quiet?.body).toMatch(/last synced 10 days ago/)
    expect(model.quiet?.resyncIds).toEqual(["c1"])
    expect(model.coreState.label).toBe("Idle")
  })
})

describe("overview flow model (example)", () => {
  it("is flagged as example", () => {
    const model = buildExampleFlowModel()
    expect(model.example).toBe(true)
    expect(model.learnings).toHaveLength(3)
  })
})
