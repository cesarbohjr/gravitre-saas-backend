import { describe, expect, it } from "vitest"
import {
  formatModelCatalogRow,
  recommendedImprovementForStatus,
  studioIntentById,
  whereUsedLabel,
} from "@/lib/intelligence/model-catalog-display"
import {
  buildModelUsageTopology,
  layoutModelUsageTopology,
} from "@/lib/intelligence/model-usage-topology"
import type { MlModelSummary } from "@/types/api"

const draft: MlModelSummary = {
  id: "m1",
  name: "Lead scorer",
  description: "Scores inbound leads",
  modelType: "classifier",
  status: "draft",
  currentVersion: 1,
  createdAt: "2026-09-01T00:00:00Z",
}

const live: MlModelSummary = {
  id: "m2",
  name: "Support copilot",
  modelType: "fine_tuned_llm",
  status: "deployed",
  currentVersion: 3,
  deployedVersion: 3,
  datasetId: "ds-1",
  baseModel: "gpt-4.1-mini",
}

describe("model-catalog-display", () => {
  it("formats business fields without raw status words as the primary label", () => {
    const row = formatModelCatalogRow(draft)
    expect(row.purpose).toBe("Scores inbound leads")
    expect(row.businessStatus).toBe("Needs training")
    expect(row.whereUsed).toBe("Not in production use yet")
    expect(row.recommendedImprovement).toContain("Model Studio")
  })

  it("marks deployed models as available to workflows", () => {
    expect(whereUsedLabel(live)).toBe("Available to workflows and agents")
    const row = formatModelCatalogRow(live)
    expect(row.performance).toContain("Live version 3")
    expect(row.learningSources).toContain("Training dataset")
  })

  it("maps studio intents to real registry types", () => {
    expect(studioIntentById("forecast")?.modelType).toBe("forecaster")
    expect(studioIntentById("improve_agent")?.modelType).toBe("fine_tuned_llm")
    expect(studioIntentById("missing")).toBeNull()
  })

  it("does not invent dollar performance", () => {
    expect(recommendedImprovementForStatus("ready")).toContain("Deploy")
    expect(formatModelCatalogRow(draft).performance).not.toContain("$")
  })
})

describe("model-usage-topology", () => {
  it("builds hub-linked nodes from catalog rows", () => {
    const rows = [formatModelCatalogRow(draft), formatModelCatalogRow(live)]
    const graph = buildModelUsageTopology(rows)
    const layout = layoutModelUsageTopology(graph)
    expect(graph.nodes.some((n) => n.kind === "hub")).toBe(true)
    expect(graph.nodes.some((n) => n.kind === "in_use")).toBe(true)
    expect(layout.positions.size).toBe(graph.nodes.length)
  })
})
