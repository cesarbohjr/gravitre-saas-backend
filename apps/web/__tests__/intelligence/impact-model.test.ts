import { describe, expect, it } from "vitest"
import {
  OUTCOME_PATH_STEP_COUNT,
  agentStatusLine,
  firstResultSteps,
  formatHours,
  formatUsd,
  impactCsv,
  impactTotals,
  orderAgentRows,
  outcomeProgress,
  returnMissingReason,
} from "@/components/intelligence/impact/impact-model"
import type { AgentRoiMetric, AgentRoiReport, AgentRoiRow, Connector } from "@/types/api"

const m = (value: number | null, provenance: AgentRoiMetric["provenance"], unit = "count"): AgentRoiMetric => ({
  label: "x",
  value,
  unit,
  provenance,
})

function row(id: string, name: string, cost: number, tasks = 0): AgentRoiRow {
  return {
    agentId: id,
    agentName: name,
    tasksCompleted: m(tasks, "operational"),
    actionsExecuted: m(tasks, "operational"),
    agentCostUsd: m(cost, "measured", "usd"),
    estimatedHoursSaved: m(0, "estimate", "hours"),
    estimatedLaborValueUsd: m(0, "estimate", "usd"),
    revenueInfluencedUsd: m(null, "not_configured", "usd"),
    roiMultiple: m(null, "insufficient_data", "x"),
  }
}

const report: AgentRoiReport = {
  orgId: "o",
  periodDays: 30,
  periodStart: "2026-09-07",
  periodEnd: "2026-10-07",
  methodology: "",
  laborUsdPerHour: { value: 50, source: "default_estimate", provenance: "estimate" },
  orgTotals: {
    tasksCompleted: m(0, "operational"),
    actionsExecuted: m(0, "operational"),
    agentCostUsd: m(0.06, "measured", "usd"),
    estimatedHoursSaved: m(0, "estimate", "hours"),
    estimatedLaborValueUsd: m(0, "estimate", "usd"),
    revenueInfluencedUsd: m(null, "not_configured", "usd"),
    roiMultiple: m(null, "insufficient_data", "x"),
  },
  agents: [row("unassigned", "Unassigned", 0.06), row("a1", "Sales Agent", 0)],
  honesty: {
    measuredFields: [],
    estimateFields: [],
    notConfiguredUnlessEvidence: [],
    moduleC: true,
    sta286: true,
  },
}

describe("impact model", () => {
  it("keeps no-evidence values as null (dash), never zero", () => {
    const t = impactTotals(report)
    expect(t.spent).toBe(0.06)
    expect(t.spentCertainty).toBe("measured")
    expect(t.hoursCertainty).toBe("estimated")
    expect(t.revenue).toBeNull()
    expect(t.revenueCertainty).toBe("none")
    expect(t.roi).toBeNull()
    expect(t.unassignedCost).toBe(0.06)
    expect(formatUsd(t.revenue)).toBe("—")
    expect(formatUsd(t.spent)).toBe("$0.06")
    expect(formatHours(0)).toBe("0 h")
    expect(returnMissingReason(t)).toBe("Needs one finished task")
  })

  it("puts the Unassigned row last and describes it", () => {
    const ordered = orderAgentRows(report.agents)
    expect(ordered.map((r) => r.agentId)).toEqual(["a1", "unassigned"])
    expect(agentStatusLine(ordered[1], undefined).text).toBe("Spend with no agent attached")
  })

  it("computes the first-result checklist from connectors and totals", () => {
    const connectors = [
      { id: "c1", name: "HubSpot", vendor: "hubspot", status: "error" } as Connector,
    ]
    const steps = firstResultSteps({
      connectors,
      totals: impactTotals(report),
      routes: { connectors: "/connectors", plays: "/plays", agents: "/agents" },
    })
    expect(steps.map((s) => s.done)).toEqual([false, false, false])
    expect(steps[0].title).toBe("Reconnect HubSpot")
    expect(steps[0].href).toBe("/connectors/c1")
  })

  it("summarises evidence progress on an outcome path", () => {
    const p = outcomeProgress({
      id: "p",
      scopeId: "p",
      scopeLabel: "Sales",
      presentStepCount: 2,
      complete: false,
      steps: [
        { kind: "objective", title: "Objective", label: "", present: true, evidence: [] },
        { kind: "signal", title: "Signal", label: "", present: true, evidence: [] },
        { kind: "agent_workflow", title: "Agent", label: "", present: false, evidence: [] },
      ],
    })
    expect(p?.summary).toBe("2 of 3 steps have evidence. The trail stops before any agent acted.")
  })

  it("exports blanks for no-evidence values in the CSV", () => {
    const csv = impactCsv({ report, period: 30 })
    expect(csv).toContain("From spend to value,Spent (USD),0.06,Measured")
    expect(csv).toContain("From spend to value,Revenue influenced (USD),,No evidence yet")
    expect(csv.trim().split("\n").at(-1)).toBe("Unassigned,0,0,,0.06")
  })
})

describe("latest outcome empty trail", () => {
  it("draws one empty segment per backend outcome path step kind", () => {
    // backend/app/services/intelligence_outcome_path.py OUTCOME_PATH_STEP_KINDS
    expect(OUTCOME_PATH_STEP_COUNT).toBe(8)
    expect(outcomeProgress(null)).toBeNull()
  })
})
