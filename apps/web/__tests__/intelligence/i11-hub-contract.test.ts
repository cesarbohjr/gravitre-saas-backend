import { describe, expect, it } from "vitest"
import {
  INTELLIGENCE_HUB_TABS,
  resolveIntelligenceHubTab,
} from "@/components/intelligence/intelligence-hub-tabs"
import { buildLensMetrics } from "@/components/intelligence/map/build-lens-metrics"

describe("I11 hub contract", () => {
  it("keeps exactly seven hub tabs and never lists Training", () => {
    expect(INTELLIGENCE_HUB_TABS).toHaveLength(7)
    expect(INTELLIGENCE_HUB_TABS.map((tab) => tab.label)).not.toContain("Training")
    expect(INTELLIGENCE_HUB_TABS.some((tab) => tab.href.includes("/training"))).toBe(false)
  })

  it("routes /training into Model Studio, not a Training tab", () => {
    expect(resolveIntelligenceHubTab("/training")).toBe("model-studio")
    expect(resolveIntelligenceHubTab("/intelligence/reports")).toBe("reports")
  })
})

describe("I11 lens UNKNOWN≠ZERO", () => {
  const base = {
    knowledgeGraph: { entity_count: 0, relationship_count: 0 },
    readiness: null,
    modelCatalog: null,
    coreState: { core: { activeAgentRuns: 0 } },
    businessImpact: null,
    outcomesByEvent: {},
    canonicalMetrics: {
      knowledge: { knownEntities: 0, knownRelationships: 0 },
      execution: { configuredActiveAgents: 0, currentlyRunningAgents: 0 },
    },
  }

  it("never shows 0 while loading or on error", () => {
    for (const loadState of ["LOADING", "UNINITIALIZED", "ERROR"] as const) {
      const metrics = buildLensMetrics({ ...base, loadState })
      for (const lens of Object.values(metrics)) {
        expect(lens.value).toBe("—")
        expect(lens.value).not.toBe("0")
      }
    }
  })
})
