/**
 * Shared explainable pre-action payload for chat confirm + Approvals.
 * Fields come from RiskApprovalEvaluator / pending_task params — do not invent.
 */

export type PreActionRiskLevel = "low" | "medium" | "high"

export type PreActionCardPayload = {
  title: string
  description?: string
  entity?: string
  action: string
  estimatedImpact?: string
  riskLevel?: PreActionRiskLevel
  approvalReason?: string
  requiresApproval: boolean
  modifyHint?: string
  source: "chat_pending" | "approvals_queue"
  conversationId?: string
  approvalId?: string
  runId?: string
}

export function normalizeRiskLevel(value: unknown): PreActionRiskLevel | undefined {
  const raw = String(value || "")
    .trim()
    .toLowerCase()
  if (raw === "low" || raw === "medium" || raw === "high") return raw
  if (raw === "critical") return "high"
  return undefined
}

export function formatImpactLabel(value: unknown): string | undefined {
  const raw = String(value || "").trim()
  if (!raw) return undefined
  return raw.replace(/_/g, " ")
}

type PendingLike = {
  type?: string
  status?: string
  params?: Record<string, unknown> | null
  current_step?: { label?: string } | null
}

export function preActionFromPendingTask(
  pending: PendingLike,
  opts?: { description?: string },
): PreActionCardPayload | null {
  if (!pending?.type) return null
  const params = (pending.params || {}) as Record<string, unknown>
  const label =
    (typeof params.label === "string" && params.label.trim()) ||
    (typeof params.invoke_action === "string" && params.invoke_action) ||
    (pending.current_step?.label && String(pending.current_step.label)) ||
    "Pending action"
  const integration =
    typeof params.integration === "string" ? params.integration.replace(/_/g, " ") : undefined
  const impact =
    formatImpactLabel(params.estimated_impact ?? params.estimatedImpact) ||
    formatImpactLabel(params.impact)
  const risk = normalizeRiskLevel(params.risk_level ?? params.riskLevel)
  const reason =
    (typeof params.approval_reason === "string" && params.approval_reason) ||
    (typeof params.approvalReason === "string" && params.approvalReason) ||
    undefined
  return {
    title: label,
    description: opts?.description,
    entity: integration,
    action: label,
    estimatedImpact: impact,
    riskLevel: risk,
    approvalReason: reason || undefined,
    requiresApproval: Boolean(
      params.requires_approval ?? params.requiresApproval ?? pending.type === "connector_action",
    ),
    modifyHint: "Tell me in chat what to change.",
    source: "chat_pending",
    conversationId:
      typeof params.conversation_id === "string"
        ? params.conversation_id
        : typeof params.conversationId === "string"
          ? params.conversationId
          : undefined,
    approvalId:
      typeof params.approval_id === "string"
        ? params.approval_id
        : typeof params.approvalId === "string"
          ? params.approvalId
          : undefined,
  }
}

type ApprovalLike = {
  id: string
  title: string
  description?: string
  context: {
    entity: string
    action: string
    impact?: string
    riskLevel?: string
    risk_level?: string
    estimatedImpact?: string
    estimated_impact?: string
    approvalReason?: string
    approval_reason?: string
    conversationId?: string
    conversation_id?: string
    runId?: string
  }
}

export function preActionFromApproval(approval: ApprovalLike): PreActionCardPayload {
  const ctx = approval.context || { entity: "", action: "" }
  const impact =
    formatImpactLabel(ctx.impact) ||
    formatImpactLabel(ctx.estimatedImpact ?? ctx.estimated_impact)
  const risk = normalizeRiskLevel(ctx.riskLevel ?? ctx.risk_level)
  const reason = ctx.approvalReason || ctx.approval_reason
  const conversationId = ctx.conversationId || ctx.conversation_id
  return {
    title: approval.title,
    description: approval.description,
    entity: ctx.entity,
    action: ctx.action,
    estimatedImpact: impact,
    riskLevel: risk,
    approvalReason: reason,
    requiresApproval: true,
    modifyHint: conversationId
      ? "Open the chat conversation to request changes."
      : "Ask the requester to revise in chat.",
    source: "approvals_queue",
    conversationId: conversationId || undefined,
    approvalId: approval.id,
    runId: ctx.runId,
  }
}
