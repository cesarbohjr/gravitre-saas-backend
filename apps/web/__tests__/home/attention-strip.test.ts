import { describe, expect, it } from "vitest"
import { buildAttentionItems } from "@/components/home/attention-strip"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"

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

describe("dashboard attention strip", () => {
  it("lists nothing when no loaded data needs attention", () => {
    expect(buildAttentionItems(data())).toEqual([])
  })

  it("only lists items backed by loaded data", () => {
    const items = buildAttentionItems(
      data({
        pendingApprovals: 2,
        pendingApprovalItems: [{ id: "a1", title: "Send renewal email" }],
        agentStatusCounts: { active: 1, idle: 0, processing: 0, error: 1 },
        revenueRisks: [
          { id: "r1", title: "Churn risk", summary: "Usage down" },
          { id: "r2", title: "Late invoice", summary: "30 days" },
          { id: "r3", title: "Third", summary: "hidden" },
        ],
      }),
    )
    expect(items.map((i) => i.id)).toEqual(["approvals", "agent-errors", "risk-r1", "risk-r2"])
    expect(items[0].title).toBe("2 approvals waiting on you")
    expect(items[0].detail).toBe("Send renewal email")
    expect(items[1].title).toBe("1 agent needs attention")
  })
})
