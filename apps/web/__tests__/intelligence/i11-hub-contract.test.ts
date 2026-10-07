import { describe, expect, it } from "vitest"
import {
  INTELLIGENCE_HUB_GROUPS,
  INTELLIGENCE_HUB_TABS,
  resolveIntelligenceHubTab,
} from "@/components/intelligence/intelligence-hub-tabs"
import { buildLensMetrics } from "@/components/intelligence/map/build-lens-metrics"

describe("I11 hub contract", () => {
  it("keeps one level of seven tabs in two groups and never lists Training or Model Studio", () => {
    expect(INTELLIGENCE_HUB_TABS).toHaveLength(7)
    expect(INTELLIGENCE_HUB_GROUPS.map((group) => group.label)).toEqual(["Understand", "Build"])
    expect(INTELLIGENCE_HUB_TABS.map((tab) => tab.label)).not.toContain("Model Studio")
    expect(INTELLIGENCE_HUB_TABS.map((tab) => tab.label)).not.toContain("Training")
    expect(INTELLIGENCE_HUB_TABS.some((tab) => tab.href?.includes("/training"))).toBe(false)
  })

  it("gives each feature one home tab", () => {
    expect(resolveIntelligenceHubTab("/intelligence/data")).toBe("data")
    expect(resolveIntelligenceHubTab("/intelligence/model-studio")).toBe("models")
    expect(resolveIntelligenceHubTab("/intelligence/models")).toBe("models")
    expect(resolveIntelligenceHubTab("/models/built-in")).toBe("models")
    expect(resolveIntelligenceHubTab("/intelligence/memory")).toBe("learning")
    expect(resolveIntelligenceHubTab("/intelligence/reports")).toBe("reports")
  })
})

describe("Intelligence vocabulary", () => {
  it("gives every tab a distinct plain-language name and purpose", () => {
    const understand = INTELLIGENCE_HUB_TABS.filter((tab) => tab.group === "understand").map((tab) => tab.label)
    const build = INTELLIGENCE_HUB_TABS.filter((tab) => tab.group === "build").map((tab) => tab.label)
    expect(understand).toEqual(["Overview", "Knowledge", "Forecasts", "Impact", "Reports"])
    expect(build).toEqual(["Data", "Models"])
    for (const tab of INTELLIGENCE_HUB_TABS) expect(tab.description.length).toBeGreaterThan(10)
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
