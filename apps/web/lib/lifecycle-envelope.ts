/**
 * Maps backend `task_state.lifecycle_envelope` (Release 2) onto existing UI contracts.
 * Single store: conversation task_state — no parallel lifecycle client state.
 */
import type { ActionStatus } from "@/types/api"

export type LifecycleCustomerStage =
  | "accepted"
  | "verifying"
  | "verified"
  | "uncertain"
  | "failed"
  | "cancelled"

export type LifecycleEnvelopeView = {
  customerStage: LifecycleCustomerStage
  semanticStage: string
  executionVerified: boolean
  uncertain: boolean
  logicalActionId?: string | null
  providerRecordId?: string | null
}

export function parseLifecycleEnvelope(taskState: Record<string, unknown> | null | undefined): LifecycleEnvelopeView | null {
  if (!taskState || typeof taskState !== "object") return null
  const raw = taskState.lifecycle_envelope
  if (!raw || typeof raw !== "object") return null
  const env = raw as Record<string, unknown>
  const customer = String(env.customer_stage || "").trim().toLowerCase()
  if (!isCustomerStage(customer)) return null
  return {
    customerStage: customer,
    semanticStage: String(env.semantic_stage || ""),
    executionVerified: Boolean(env.execution_verified),
    uncertain: Boolean(env.uncertain),
    logicalActionId: env.logical_action_id ? String(env.logical_action_id) : null,
    providerRecordId: env.provider_record_id ? String(env.provider_record_id) : null,
  }
}

function isCustomerStage(value: string): value is LifecycleCustomerStage {
  return (
    value === "accepted" ||
    value === "verifying" ||
    value === "verified" ||
    value === "uncertain" ||
    value === "failed" ||
    value === "cancelled"
  )
}

/** Aligns lifecycle envelope with existing ActionStatus (types/api.ts). */
export function actionStatusFromLifecycle(envelope: LifecycleEnvelopeView | null): ActionStatus | null {
  if (!envelope) return null
  switch (envelope.customerStage) {
    case "accepted":
      return "pending_approval"
    case "verifying":
      return "verifying"
    case "verified":
      return "completed"
    case "uncertain":
      return "verifying"
    case "failed":
      return "failed"
    case "cancelled":
      return "cancelled"
    default:
      return null
  }
}

/**
 * Prefer lifecycle envelope when present; otherwise fall back to legacy pending_task status.
 * Does not grant authority — display only.
 */
export function resolveTaskActionStatus(
  taskState: Record<string, unknown> | null | undefined,
  pendingTask?: { status?: string | null } | null,
): ActionStatus | null {
  const fromEnvelope = actionStatusFromLifecycle(parseLifecycleEnvelope(taskState))
  if (fromEnvelope) return fromEnvelope
  const legacy = String(pendingTask?.status || "").trim().toLowerCase()
  if (legacy === "pending_approval" || legacy === "awaiting_approval") return "pending_approval"
  if (legacy === "running" || legacy === "executing") return "running"
  if (legacy === "completed") return "completed"
  if (legacy === "failed") return "failed"
  if (legacy === "cancelled") return "cancelled"
  return null
}

/** Monotonic merge: ignore stale background patches when turn_id regresses. */
export function mergeTaskStateMonotonic(
  current: Record<string, unknown> | null | undefined,
  incoming: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null {
  if (!incoming || typeof incoming !== "object") return current ?? null
  if (!current || typeof current !== "object") return incoming
  const curTurn = String(current.turn_id || current.turnId || "")
  const nextTurn = String(incoming.turn_id || incoming.turnId || "")
  if (curTurn && nextTurn && curTurn !== nextTurn) {
    // Same conversation, different turn — keep newer turn only when incoming is explicitly newer seq.
    const curSeq = Number(current.task_revision ?? current.taskRevision ?? 0)
    const nextSeq = Number(incoming.task_revision ?? incoming.taskRevision ?? 0)
    if (nextSeq > 0 && curSeq > 0 && nextSeq < curSeq) return current
  }
  return { ...current, ...incoming }
}
