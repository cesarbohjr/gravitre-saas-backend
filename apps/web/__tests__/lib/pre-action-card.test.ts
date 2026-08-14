import { describe, expect, it } from "vitest"
import {
  normalizeRiskLevel,
  preActionFromApproval,
  preActionFromPendingTask,
} from "@/lib/pre-action-card"

describe("pre-action-card mappers", () => {
  it("maps pending connector params into explainable payload", () => {
    const payload = preActionFromPendingTask({
      type: "connector_action",
      status: "awaiting_confirm",
      params: {
        label: "Create HubSpot note",
        invoke_action: "hubspot.notes.create",
        integration: "hubspot",
        estimated_impact: "medium",
        risk_level: "high",
        approval_reason: "Destructive write",
        requires_approval: true,
      },
    })
    expect(payload?.estimatedImpact).toBe("medium")
    expect(payload?.riskLevel).toBe("high")
    expect(payload?.approvalReason).toBe("Destructive write")
    expect(payload?.action).toBe("hubspot.notes.create")
    expect(payload?.source).toBe("chat_pending")
  })

  it("maps approval context impact/risk for Approvals queue", () => {
    const payload = preActionFromApproval({
      id: "appr-1",
      title: "Approve chat write",
      description: "Member requested write",
      context: {
        entity: "Hubspot",
        action: "Create note",
        impact: "medium",
        risk_level: "high",
        conversation_id: "conv-1",
      },
    })
    expect(payload.estimatedImpact).toBe("medium")
    expect(payload.riskLevel).toBe("high")
    expect(payload.conversationId).toBe("conv-1")
    expect(payload.source).toBe("approvals_queue")
  })

  it("normalizes critical risk to high", () => {
    expect(normalizeRiskLevel("critical")).toBe("high")
  })
})
