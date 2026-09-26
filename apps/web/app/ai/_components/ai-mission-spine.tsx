"use client"

import type { UIMessage } from "ai"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { HostedFileRef } from "@/components/gravitre/assistant/file-reference-chip"
import type { AiRuntimeState } from "@/lib/gravitre-ai-runtime-state"
import { cn } from "@/lib/utils"

export type MissionStageId = "objective" | "plan" | "work" | "artifact" | "approval" | "result"
export type MissionStageState = "done" | "current" | "attention" | "failed" | "pending" | "not_needed"

export type MissionStage = {
  id: MissionStageId
  label: string
  state: MissionStageState
  detail: string
}

export const MISSION_STAGE_ORDER: Array<{ id: MissionStageId; label: string; explain: string }> = [
  { id: "objective", label: "Objective", explain: "You state the outcome you want." },
  { id: "plan", label: "Plan", explain: "Gravitre proposes the steps and the tools it will use." },
  { id: "work", label: "Work", explain: "Agents execute through your connected systems." },
  { id: "artifact", label: "Artifact", explain: "Files, records and reports you can open." },
  { id: "approval", label: "Approval", explain: "Changes to your systems wait for your decision." },
  { id: "result", label: "Result", explain: "What happened, with the evidence behind it." },
]

function firstUserText(messages: UIMessage[]): string | null {
  const first = messages.find((message) => message.role === "user")
  if (!first) return null
  const text = (first.parts ?? [])
    .map((part) => (part && typeof part === "object" && "text" in part && typeof part.text === "string" ? part.text : ""))
    .join(" ")
    .trim()
  return text || null
}

/**
 * Where the current request stands, derived only from the live conversation,
 * task, progress and result props. A stage with no signal stays pending.
 */
export function deriveMissionStages(input: {
  messages: UIMessage[]
  runtimeState: AiRuntimeState
  progressSteps?: string[] | null
  pendingTask?: ChatPendingTask | null
  executionResult?: ChatExecutionResult | null
  hostedFiles?: HostedFileRef[] | null
}): MissionStage[] {
  const { messages, runtimeState, progressSteps, pendingTask, executionResult, hostedFiles } = input
  const objective = firstUserText(messages)
  const planSteps = progressSteps?.length ?? pendingTask?.params?.steps?.length ?? pendingTask?.params?.total_steps ?? 0
  const working = runtimeState === "streaming" || runtimeState === "generating"
  const hasReply = messages.some((message) => message.role === "assistant")
  const artifactCount = (hostedFiles?.length ?? 0) + (executionResult?.artifacts?.length ?? 0)
  const approvalOpen = runtimeState === "needs_approval" || runtimeState === "blocked"
  const failed = runtimeState === "failed" || executionResult?.success === false
  const delivered = executionResult?.success === true

  const stages: Record<MissionStageId, Omit<MissionStage, "id" | "label">> = {
    objective: objective
      ? { state: "done", detail: objective }
      : { state: "current", detail: "Waiting for your request" },
    plan:
      planSteps > 0
        ? { state: working && !hasReply ? "current" : "done", detail: `${planSteps} step${planSteps === 1 ? "" : "s"}` }
        : { state: "pending", detail: "No plan reported" },
    work: working
      ? { state: "current", detail: runtimeState === "generating" ? "Executing" : "Responding" }
      : hasReply
        ? { state: "done", detail: "Replied" }
        : { state: "pending", detail: "Not started" },
    artifact:
      artifactCount > 0
        ? { state: "done", detail: `${artifactCount} output${artifactCount === 1 ? "" : "s"}` }
        : { state: "pending", detail: "None yet" },
    approval: approvalOpen
      ? { state: "attention", detail: runtimeState === "blocked" ? "Queued for an approver" : "Waiting for you" }
      : pendingTask || executionResult
        ? { state: "done", detail: "Resolved" }
        : { state: "not_needed", detail: "Not requested" },
    result: failed
      ? { state: "failed", detail: "Did not complete" }
      : delivered
        ? { state: "done", detail: executionResult?.title?.trim() || "Delivered" }
        : (runtimeState === "completed" || runtimeState === "idle") && hasReply
          ? { state: "done", detail: "Answered" }
          : { state: "pending", detail: "—" },
  }

  return MISSION_STAGE_ORDER.map((stage) => ({ id: stage.id, label: stage.label, ...stages[stage.id] }))
}

const MARKER: Record<MissionStageState, string> = {
  done: "bg-[color:var(--g-text-primary)] border-[color:var(--g-text-primary)]",
  current: "bg-[color:var(--g-brand)] border-[color:var(--g-brand)] animate-pulse motion-reduce:animate-none",
  attention: "bg-warning border-warning",
  failed: "bg-destructive border-destructive",
  pending: "bg-transparent border-[color:var(--g-border-strong)]",
  not_needed: "bg-transparent border-dashed border-[color:var(--g-border-default)]",
}

const STATE_LABEL: Record<MissionStageState, string> = {
  done: "done",
  current: "in progress",
  attention: "needs you",
  failed: "failed",
  pending: "not started",
  not_needed: "not needed",
}

/** Vertical mission rail beside the work (desktop); a compact stage strip on narrow widths. */
export function AiMissionSpine({ stages, className }: { stages: MissionStage[]; className?: string }) {
  return (
    <>
      <ol
        aria-label="Request progress"
        data-gravitre-ai-mission=""
        className={cn("flex shrink-0 items-center gap-3 overflow-x-auto border-b border-divide px-3 py-2 lg:hidden", className)}
      >
        {stages.map((stage) => (
          <li key={stage.id} className="flex shrink-0 items-center gap-1.5 text-[11.5px]">
            <span aria-hidden className={cn("size-2 rounded-full border", MARKER[stage.state])} />
            <span className={cn(stage.state === "pending" || stage.state === "not_needed" ? "text-muted-foreground" : "text-foreground")}>
              {stage.label}
            </span>
            <span className="sr-only">: {STATE_LABEL[stage.state]}</span>
          </li>
        ))}
      </ol>
      <aside
        aria-label="Request progress"
        data-gravitre-ai-mission-rail=""
        className="hidden w-[232px] shrink-0 flex-col overflow-y-auto border-r border-divide bg-[color:var(--g-rail-bg)] lg:flex"
      >
        <ol className="relative flex flex-col px-4 py-4">
          {stages.map((stage, index) => (
            <li key={stage.id} className="relative flex gap-3 pb-5 last:pb-0">
              {index < stages.length - 1 ? (
                <span aria-hidden className="absolute left-[4.5px] top-3 h-[calc(100%-6px)] w-px bg-[color:var(--g-border-default)]" />
              ) : null}
              <span aria-hidden className={cn("relative z-10 mt-1 size-2.5 shrink-0 rounded-full border", MARKER[stage.state])} />
              <div className="min-w-0 flex-1">
                <p className="flex items-baseline justify-between gap-2 text-[12.5px] font-semibold text-foreground">
                  {stage.label}
                  <span
                    className={cn(
                      "text-[11px] font-medium",
                      stage.state === "attention" && "text-warning",
                      stage.state === "failed" && "text-destructive",
                      stage.state === "current" && "text-[color:var(--g-brand)]",
                      (stage.state === "done" || stage.state === "pending" || stage.state === "not_needed") && "text-muted-foreground",
                    )}
                  >
                    {STATE_LABEL[stage.state]}
                  </span>
                </p>
                <p
                  className={cn(
                    "mt-0.5 text-[12px] leading-snug text-muted-foreground",
                    stage.id === "objective" ? "line-clamp-4 text-foreground" : "line-clamp-2",
                  )}
                >
                  {stage.detail}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </aside>
    </>
  )
}
