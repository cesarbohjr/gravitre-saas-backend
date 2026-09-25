"use client"

import { useState, type ReactNode } from "react"
import type { UIMessage } from "ai"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import { GravitreAIRuntimeStatus } from "@/components/gravitre/ai-runtime-status"
import {
  GravitreInspector,
  GravitreInspectorFields,
  GravitreInspectorNotice,
  GravitreInspectorSection,
  type GravitreInspectorKind,
} from "@/components/gravitre/inspector"
import { AI_RUNTIME_STATE_COPY, type AiRuntimeState } from "@/lib/gravitre-ai-runtime-state"

/** States that describe a settled turn worth inspecting. Live states change too fast to read. */
const INSPECTABLE: ReadonlySet<AiRuntimeState> = new Set(["completed", "failed", "partial", "needs_approval", "blocked"])

export function runtimeInspectorKind(state: AiRuntimeState): GravitreInspectorKind {
  if (state === "failed") return "error"
  if (state === "needs_approval" || state === "blocked") return "approval"
  return "task"
}

type Field = { label: string; value: ReactNode; mono?: boolean }

function present(fields: Array<Field | false | null | undefined>): Field[] {
  return fields.filter((f): f is Field => Boolean(f) && (f as Field).value !== undefined && (f as Field).value !== null && (f as Field).value !== "")
}

/**
 * Every field comes from values the bridges already receive from `AiWorkspace`.
 * Nothing is inferred: a field the runtime did not report is omitted, not guessed.
 */
export function runtimeInspectorFields({
  state,
  conversationId,
  messages,
  executionResult,
  pendingTask,
}: {
  state: AiRuntimeState
  conversationId?: string | null
  messages: UIMessage[]
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
}) {
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant")
  const turn = present([
    { label: "Status", value: AI_RUNTIME_STATE_COPY[state].label },
    { label: "Conversation", value: conversationId ?? "Not saved yet", mono: Boolean(conversationId) },
    lastAssistant && { label: "Last reply", value: lastAssistant.id, mono: true },
  ])
  const steps = executionResult?.structured?.stepBreakdown ?? []
  const failedSteps = steps.filter((s) => s?.success === false).length
  const result = executionResult
    ? present([
        { label: "Outcome", value: executionResult.success === true ? "Succeeded" : executionResult.success === false ? "Failed" : undefined },
        { label: "Action", value: executionResult.task_label ?? executionResult.title },
        { label: "Integration", value: executionResult.integration ?? undefined },
        Boolean(executionResult.entity_id) && {
          label: "Record",
          value: [executionResult.entity_type, executionResult.entity_id].filter(Boolean).join(" · "),
          mono: true,
        },
        { label: "Run", value: executionResult.structured?.runId ?? undefined, mono: true },
        steps.length > 0 && { label: "Steps", value: failedSteps ? `${steps.length - failedSteps} of ${steps.length} finished` : `${steps.length} finished` },
      ])
    : []
  const task = pendingTask
    ? present([
        { label: "Action", value: pendingTask.params?.label ?? pendingTask.params?.invoke_action ?? pendingTask.type },
        { label: "Integration", value: pendingTask.params?.integration },
        { label: "Status", value: pendingTask.status },
        { label: "Risk", value: pendingTask.params?.risk_level },
        { label: "Reason", value: pendingTask.params?.approval_reason },
        { label: "Approval", value: pendingTask.params?.approval_id, mono: true },
      ])
    : []
  return { turn, result, task }
}

/**
 * Runtime status line plus the shared inspector for the current turn. Approve and
 * Reject stay in the conversation's execution panel; the inspector only explains.
 */
export function GravitreAIRuntimeDetails({
  state,
  conversationId,
  messages,
  executionResult,
  pendingTask,
  inspectorSide = "right",
}: {
  state: AiRuntimeState
  conversationId?: string | null
  messages: UIMessage[]
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
  inspectorSide?: "right" | "bottom"
}) {
  const [open, setOpen] = useState(false)
  const inspectable = INSPECTABLE.has(state)
  const kind = runtimeInspectorKind(state)
  const { turn, result, task } = runtimeInspectorFields({ state, conversationId, messages, executionResult, pendingTask })

  return (
    <>
      <GravitreAIRuntimeStatus
        state={state}
        action={
          inspectable ? (
            <button
              type="button"
              onClick={() => setOpen(true)}
              data-gravitre-ai-runtime-details=""
              className="rounded-sm px-1.5 py-0.5 text-[11px] font-medium text-[color:var(--g-text-secondary)] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40"
            >
              Details
            </button>
          ) : null
        }
      />
      {inspectable ? (
        <GravitreInspector
          open={open}
          onOpenChange={setOpen}
          kind={kind}
          side={inspectorSide}
          title={AI_RUNTIME_STATE_COPY[state].label}
          description={AI_RUNTIME_STATE_COPY[state].detail}
        >
          {state === "failed" ? (
            <GravitreInspectorNotice tone="error" title="This turn did not report completion to your browser">
              The conversation shows what was received. Reopen it to load what Gravitre saved.
            </GravitreInspectorNotice>
          ) : state === "needs_approval" || state === "blocked" ? (
            <GravitreInspectorNotice tone="approval" title={AI_RUNTIME_STATE_COPY[state].label}>
              Approve or reject in the conversation. Nothing runs from this panel.
            </GravitreInspectorNotice>
          ) : null}
          <GravitreInspectorSection title="Turn">
            <GravitreInspectorFields fields={turn} />
          </GravitreInspectorSection>
          {task.length > 0 ? (
            <GravitreInspectorSection title="Pending action">
              <GravitreInspectorFields fields={task} />
            </GravitreInspectorSection>
          ) : null}
          {result.length > 0 ? (
            <GravitreInspectorSection title="Result">
              <GravitreInspectorFields fields={result} />
            </GravitreInspectorSection>
          ) : null}
        </GravitreInspector>
      ) : null}
    </>
  )
}
