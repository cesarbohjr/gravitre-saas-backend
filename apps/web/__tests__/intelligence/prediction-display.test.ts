import { describe, expect, it } from "vitest"
import {
  classifyPredictionKind,
  filterPredictionsByDepartment,
  formatPredictionRow,
  formatPredictions,
  partitionPredictionsByKind,
} from "@/lib/intelligence/prediction-display"
import { buildPredictionTopology, layoutPredictionTopology } from "@/lib/intelligence/prediction-topology"

describe("prediction-display", () => {
  it("classifies risk, opportunity, and signal kinds", () => {
    expect(classifyPredictionKind("risk")).toBe("risk")
    expect(classifyPredictionKind("alert")).toBe("risk")
    expect(classifyPredictionKind("opportunity")).toBe("opportunity")
    expect(classifyPredictionKind("prediction")).toBe("signal")
  })

  it("maps canonical prediction fields without raw status strings", () => {
    const row = formatPredictionRow({
      id: "p1",
      type: "risk",
      businessStatement: "Support backlog may spike next week",
      horizon: "7 days",
      confidence: 0.82,
      objective: "Reduce SLA breaches",
      subject: "Ticket volume",
      sourceModel: "sla_predictor",
      evidence: ["Past 3 Monday spikes"],
      recommendedActions: ["Pre-schedule coverage"],
      department: "support",
      qualityFlags: [],
      status: "active",
    })
    expect(row.statement).toContain("Support backlog")
    expect(row.kind).toBe("risk")
    expect(row.horizon).toBe("7 days")
    expect(row.evidence).toHaveLength(1)
    expect(row.actions).toContain("Pre-schedule coverage")
    expect(row.drivers.some((d) => d.includes("sla_predictor"))).toBe(true)
  })

  it("flags unscoped predictions for honest banner copy", () => {
    const [row] = formatPredictions([
      {
        id: "u1",
        businessStatement: "Unscoped domain signal",
        qualityFlags: ["UNSCOPED_PREDICTION"],
      },
    ])
    expect(row.isUnscoped).toBe(true)
    expect(row.qualityNotes[0]).toContain("connected source")
  })

  it("filters by department", () => {
    const rows = formatPredictions([
      { id: "1", businessStatement: "A", department: "sales" },
      { id: "2", businessStatement: "B", department: "support" },
    ])
    const salesOnly = filterPredictionsByDepartment(rows, "sales")
    expect(salesOnly).toHaveLength(1)
    expect(salesOnly[0]?.statement).toBe("A")
  })

  it("partitions predictions for topology", () => {
    const rows = formatPredictions([
      { id: "r", businessStatement: "Risk", type: "risk" },
      { id: "o", businessStatement: "Opp", type: "opportunity" },
    ])
    const parts = partitionPredictionsByKind(rows)
    expect(parts.risks).toHaveLength(1)
    expect(parts.opportunities).toHaveLength(1)
  })
})

describe("prediction-topology", () => {
  it("builds hub-linked risk and opportunity nodes", () => {
    const risks = formatPredictions([{ id: "r1", businessStatement: "Risk one", type: "risk" }])
    const opps = formatPredictions([
      { id: "o1", businessStatement: "Opp one", type: "opportunity" },
    ])
    const graph = buildPredictionTopology(risks, opps, [])
    const layout = layoutPredictionTopology(graph)
    expect(layout.nodes.some((n) => n.kind === "hub")).toBe(true)
    expect(layout.edges.length).toBeGreaterThan(0)
    expect(layout.positions.size).toBe(layout.nodes.length)
  })
})
