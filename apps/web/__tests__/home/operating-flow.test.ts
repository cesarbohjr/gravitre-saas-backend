import { describe, expect, it } from "vitest"
import { buildFlowLanes } from "@/components/home/operating-flow"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"
import type { DemoAssignment } from "@/lib/demo-assignments"

function data(overrides: Partial<HomeDashboardData> = {}): HomeDashboardData {
  return {
    agents: [],
    activeAgents: null,
    agentTotal: null,
    agentStatusCounts: null,
    metrics: {} as HomeDashboardData["metrics"],
    aiOs: {} as HomeDashboardData["aiOs"],
    pendingApprovals: 0,
    pendingApprovalItems: [],
    avgConfidence: null,
    queryRows: 0,
    queryRowsNeeded: 0,
    workflowRows: 0,
    workflowRowsNeeded: 0,
    hasLearningSnapshot: false,
    revenueRisks: [],
    predictiveSummary: null,
    readyModelCount: null,
    learningVelocity: null,
    mostUsedModel: null,
    ...overrides,
  }
}

function assignment(overrides: Partial<DemoAssignment>): DemoAssignment {
  return {
    id: "job_1",
    title: "Enrich accounts",
    brief: "Enrich accounts",
    agent: { name: "Agent", role: "AI Agent", gradient: "", icon: "bot" } as DemoAssignment["agent"],
    status: "running",
    progress: Number.NaN,
    steps: [],
    createdAt: "",
    outputTypes: ["Task"],
    destination: "Review",
    ...overrides,
  }
}

describe("dashboard operating flow lanes", () => {
  it("returns the five lanes in operating order", () => {
    const lanes = buildFlowLanes(data(), [], [])
    expect(lanes.map((lane) => lane.id)).toEqual(["changed", "needs", "running", "risk", "next"])
  })

  it("leaves lanes empty when nothing is loaded instead of inventing items", () => {
    const lanes = buildFlowLanes(data({ agentTotal: 2 }), undefined, [])
    for (const id of ["changed", "needs", "running", "risk"]) {
      expect(lanes.find((lane) => lane.id === id)?.items).toEqual([])
    }
  })

  it("routes real approvals, running and failed assignments, and risks into their lanes", () => {
    const lanes = buildFlowLanes(
      data({
        pendingApprovals: 6,
        pendingApprovalItems: [
          { id: "a1", title: "Send renewal email" },
          { id: "a2", title: "Update CRM stage" },
        ],
        revenueRisks: [{ id: "r1", title: "Churn risk", summary: "Usage down" }],
      }),
      [
        assignment({ id: "run", status: "running" }),
        assignment({ id: "fail", status: "failed", title: "Sync invoices", blocker: "Token expired" }),
        assignment({ id: "decide", status: "needs_approval", title: "Renewal outreach" }),
      ],
      [],
    )
    const lane = (id: string) => lanes.find((entry) => entry.id === id)!
    const needs = lane("needs").items.map((item) => item.title)
    expect(needs).toContain("Send renewal email")
    expect(needs).toContain("Renewal outreach")
    expect(needs.some((title) => title.includes("more approval"))).toBe(true)
    expect(lane("running").items.map((item) => item.id)).toEqual(expect.arrayContaining([expect.stringContaining("run")]))
    const risk = lane("risk").items.map((item) => item.title)
    expect(risk).toContain("Churn risk")
    expect(risk).toContain("Sync invoices")
  })
})
