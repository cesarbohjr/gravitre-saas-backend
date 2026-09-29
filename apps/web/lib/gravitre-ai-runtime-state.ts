/**
 * AI workspace runtime state — presentation derivation (3.0 Plus Slice 1).
 *
 * Every state is derived from values `AiWorkspace` already passes to the bridges.
 * Nothing here invents progress: if the runtime has not reported it, the state is
 * not shown. Approval rules mirror `ChatExecutionPanel` exactly so the status line
 * can never disagree with the panel that holds the Approve button.
 *
 * `resumed` has no production signal today (no bridge prop reports a resumed run),
 * so `deriveAiRuntimeState` never returns it. It exists for the vocabulary and for
 * clearly-labelled fixture previews only.
 */

import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"

export const AI_RUNTIME_STATES = [
  "idle",
  "streaming",
  "generating",
  "completed",
  "needs_approval",
  "blocked",
  "failed",
  "partial",
  "resumed",
] as const

export type AiRuntimeState = (typeof AI_RUNTIME_STATES)[number]

/** States `deriveAiRuntimeState` can produce from production props. */
export const AI_RUNTIME_STATES_WITH_PRODUCTION_SIGNAL: readonly AiRuntimeState[] = AI_RUNTIME_STATES.filter(
  (state) => state !== "resumed",
)

export interface AiRuntimeStateInput {
  status: "ready" | "submitted" | "streaming" | "error"
  isStreaming?: boolean
  isBusy?: boolean
  dialogueMode?: string | null
  pendingTask?: ChatPendingTask | null
  executionResult?: ChatExecutionResult | null
  confirmExecuting?: boolean
  canApprove?: boolean
  canContinueAfterStop?: boolean
}

/** Same predicate `ChatExecutionPanel` uses to render the approval card. */
export function isApprovalPanelVisible(input: Pick<AiRuntimeStateInput, "dialogueMode" | "pendingTask">): boolean {
  return (
    (input.dialogueMode === "confirm" || input.dialogueMode === "awaiting_approval") &&
    Boolean(input.pendingTask?.type)
  )
}

/** Same predicate `ChatExecutionPanel` uses for "sent to an approver" copy. */
export function isQueuedForApprover(
  input: Pick<AiRuntimeStateInput, "dialogueMode" | "pendingTask" | "canApprove">,
): boolean {
  return (
    input.dialogueMode === "awaiting_approval" ||
    input.pendingTask?.status === "awaiting_admin_approval" ||
    (input.dialogueMode === "confirm" && !input.canApprove && input.pendingTask?.status !== "awaiting_confirm")
  )
}

function hasFailedStep(result: ChatExecutionResult): boolean {
  return (result.structured?.stepBreakdown ?? []).some((step) => step?.success === false)
}

export function deriveAiRuntimeState(input: AiRuntimeStateInput): AiRuntimeState {
  if (input.status === "error") return "failed"

  const result = input.executionResult
  if (result && result.success === false) return "failed"

  if (input.confirmExecuting) return "generating"

  if (isApprovalPanelVisible(input)) {
    return isQueuedForApprover(input) ? "blocked" : "needs_approval"
  }

  if (input.status === "streaming" || input.isStreaming) return "streaming"
  if (input.status === "submitted" || input.isBusy) return "generating"

  if (input.canContinueAfterStop) return "partial"

  if (result && result.success === true) {
    return hasFailedStep(result) ? "partial" : "completed"
  }

  return "idle"
}

export const AI_RUNTIME_STATE_COPY: Record<AiRuntimeState, { label: string; detail: string }> = {
  idle: { label: "Ready", detail: "Waiting for your next instruction." },
  streaming: { label: "Responding", detail: "The reply is streaming in." },
  generating: { label: "Working", detail: "Gravitre is working on this turn." },
  completed: { label: "Completed", detail: "The last action finished." },
  needs_approval: { label: "Needs your approval", detail: "Review the action below before it runs." },
  blocked: { label: "Waiting on an approver", detail: "Sent for approval. Nothing runs until it is approved." },
  failed: { label: "Did not complete", detail: "See the details below for what went wrong." },
  partial: { label: "Partially complete", detail: "Some steps did not finish. See the breakdown below." },
  resumed: { label: "Resumed", detail: "Picked up where the previous run stopped." },
}
