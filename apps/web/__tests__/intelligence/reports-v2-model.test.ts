import { describe, expect, it } from "vitest"
import type { IntelligencePageContextResponse, OutcomeAttributionPath } from "@/lib/api"
import {
  buildTemplateKpis,
  connectorsNeedingSignIn,
  pickTrailPath,
  toTrailSteps,
  trailHeadline,
} from "@/components/intelligence/reports/report-model"
import type { Connector } from "@/types/api"

function path(present: string[], extra: Partial<OutcomeAttributionPath> = {}): OutcomeAttributionPath {
  const kinds = ["objective", "signal", "prediction", "agent_workflow", "action", "outcome", "business_impact", "learning"] as const
  const steps = kinds.map((kind) => ({
    kind,
    title: kind,
    label: present.includes(kind) ? `${kind} label` : "Not enough verified data yet",
    present: present.includes(kind),
    evidence: present.includes(kind) ? ["Real proof line", "Linked record abc", "2026-10-01 09:00:00"] : [],
    sourceRecordId: present.includes(kind) ? `rec-${kind}` : null,
  }))
  return {
    id: "path:org",
    scopeId: "org",
    scopeLabel: "Organization",
    steps,
    presentStepCount: steps.filter((s) => s.present).length,
    complete: false,
    ...extra,
  }
}

function ctx(overrides: Partial<IntelligencePageContextResponse["snapshot"]> = {}, paths: OutcomeAttributionPath[] = []) {
  const metrics = {
    knowledge: {},
    learning: {},
    predictions: { activePredictions: 2, highPriorityPredictions: 1 },
    execution: { awaitingApproval: 3 },
    outcomes: { measuredOutcomes: 0 },
  }
  return {
    snapshot: {
      generatedAt: "2026-10-07T00:00:00Z",
      tenantId: "t",
      timeWindowHours: 168,
      coreState: "idle",
      agents: [],
      predictions: [
        { id: "p1", type: "risk", businessStatement: "Next run will likely fail" },
        { id: "p2", type: "opportunity", businessStatement: "Upsell" },
      ],
      learnings: [],
      metrics,
      qualityFlags: [],
      departments: [],
      ...overrides,
    },
    graph: { nodes: [], edges: [] },
    activeLens: "improves",
    availableLenses: [],
    metrics,
    qualityFlags: [],
    suggestedQuestions: [],
    outcomePaths: paths,
  } as IntelligencePageContextResponse
}

describe("reports v2 evidence trail", () => {
  it("maps the backend path to the seven design steps and drops learning", () => {
    const steps = toTrailSteps(path(["objective", "signal", "prediction", "learning"]))
    expect(steps).toHaveLength(7)
    expect(steps.filter((s) => s.present)).toHaveLength(3)
    expect(steps[3]).toMatchObject({ kind: "agent_workflow", present: false, label: "Not yet", sourceRecordId: null })
  })

  it("keeps raw ids and timestamps out of proof, using them for the source record instead", () => {
    const [objective] = toTrailSteps(path(["objective"]))
    expect(objective?.proof).toEqual(["Real proof line"])
    expect(objective?.recordedAt).toBe("2026-10-01 09:00:00")
    expect(objective?.sourceRecordId).toBe("rec-objective")
  })

  it("picks the path with the most evidence and headlines its furthest step", () => {
    const best = pickTrailPath([path(["objective"]), path(["objective", "signal", "prediction"], { id: "p2" })])
    expect(best?.id).toBe("p2")
    expect(trailHeadline(toTrailSteps(best), best)).toBe("prediction label")
  })

  it("returns no steps when there is no path", () => {
    expect(toTrailSteps(null)).toEqual([])
    expect(pickTrailPath([])).toBeNull()
  })
})

describe("reports v2 stat cards", () => {
  it("business cards use measured outcomes, trail steps and show no evidence for revenue without tracking", () => {
    const kpis = buildTemplateKpis("business", {
      pageContext: ctx({}, [path(["objective", "signal", "prediction"])]),
      metricsReady: true,
      roi: {
        orgTotals: { revenueInfluencedUsd: { label: "Revenue", value: null, provenance: "not_configured" } },
        agents: [],
      } as never,
    })
    expect(kpis.map((k) => k.value)).toEqual(["0", "3 of 7", "—"])
    expect(kpis[2]).toMatchObject({ evidence: "none", note: "Turn on revenue tracking" })
  })

  it("never shows a false zero before the snapshot is ready", () => {
    const kpis = buildTemplateKpis("business", { pageContext: undefined, metricsReady: false, roiLoading: true })
    expect(kpis.every((k) => k.value === "—")).toBe(true)
  })

  it("prediction track record stays empty until forecasts are scored", () => {
    const kpis = buildTemplateKpis("prediction", { pageContext: ctx(), metricsReady: true })
    expect(kpis[0]).toMatchObject({ value: "2", note: "1 risk · 1 opportunity" })
    expect(kpis[2]).toMatchObject({ value: "—", evidence: "none" })
    const scored = buildTemplateKpis("prediction", {
      pageContext: ctx({ outcomes: [{ event: "prediction_validated" }, { event: "prediction_missed" }] }),
      metricsReady: true,
    })
    expect(scored[2]).toMatchObject({ value: "50%", evidence: "measured" })
  })

  it("governance counts connectors waiting on sign-in and audit events", () => {
    const connectors = [
      { id: "1", name: "HubSpot", vendor: "hubspot", status: "pending" },
      { id: "2", name: "Slack", vendor: "slack", status: "active" },
    ] as Connector[]
    expect(connectorsNeedingSignIn(connectors).map((c) => c.name)).toEqual(["HubSpot"])
    const kpis = buildTemplateKpis("governance", { pageContext: ctx(), metricsReady: true, connectors, auditTotal: 0 })
    expect(kpis.map((k) => k.value)).toEqual(["3", "1", "0"])
    expect(kpis[1]?.note).toBe("HubSpot")
    const failed = buildTemplateKpis("governance", { pageContext: ctx(), metricsReady: true, connectors, auditError: true })
    expect(failed[2]).toMatchObject({ value: "—", evidence: "none" })
  })
})
