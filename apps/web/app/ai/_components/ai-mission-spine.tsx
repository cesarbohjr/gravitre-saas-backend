"use client"

import type { UIMessage } from "ai"
import { Ban, Check, Circle, Clock, Hand, Loader2, Minus, PackageCheck, X, type LucideIcon } from "lucide-react"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { HostedFileRef } from "@/components/gravitre/assistant/file-reference-chip"
import type { AiRuntimeState } from "@/lib/gravitre-ai-runtime-state"
import { cn } from "@/lib/utils"

export type MissionStageId = "objective" | "plan" | "work" | "artifact" | "approval" | "result"
export type MissionStageState =
  | "complete"
  | "active"
  | "waiting"
  | "pending"
  | "blocked"
  | "approval"
  | "available"
  | "failed"
  | "not_needed"

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

function textOf(message: UIMessage | undefined): string | null {
  if (!message) return null
  const text = (message.parts ?? [])
    .map((part) => (part && typeof part === "object" && "text" in part && typeof part.text === "string" ? part.text : ""))
    .join(" ")
    .trim()
  return text || null
}

/**
 * Where the current request stands, derived only from the live conversation,
 * runtime state, task, progress and result props. A stage with no signal stays
 * "not started" — nothing is inferred or filled in.
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
  const lastUserIndex = messages.map((message) => message.role).lastIndexOf("user")
  const objective = lastUserIndex >= 0 ? textOf(messages[lastUserIndex]) : null
  const turnReplied = messages.slice(lastUserIndex + 1).some((message) => message.role === "assistant" && textOf(message))
  const planSteps = progressSteps?.length ?? pendingTask?.params?.steps?.length ?? pendingTask?.params?.total_steps ?? 0
  const artifactCount = (hostedFiles?.length ?? 0) + (executionResult?.artifacts?.length ?? 0)

  const waitingFirstResponse = runtimeState === "generating" && !turnReplied && !pendingTask
  const executing = runtimeState === "generating" && !waitingFirstResponse
  const streaming = runtimeState === "streaming"
  const working = streaming || runtimeState === "generating"
  const approvalOpen = runtimeState === "needs_approval" || runtimeState === "blocked"
  const failed = runtimeState === "failed" || executionResult?.success === false
  const partial = runtimeState === "partial"
  const delivered = executionResult?.success === true && !partial
  const pendingStatus = String(pendingTask?.status || "").toLowerCase()
  const approvalWasRequired = pendingTask?.params?.requires_approval === true
  const approvalResolved =
    approvalWasRequired &&
    ["executed", "completed", "verified", "failed", "cancelled", "rejected", "declined"].includes(pendingStatus)

  const stages: Record<MissionStageId, Omit<MissionStage, "id" | "label">> = {
    objective: objective ? { state: "complete", detail: objective } : { state: "pending", detail: "Waiting for your request" },
    plan:
      planSteps > 0
        ? {
            state: working && !turnReplied ? "active" : "complete",
            detail: `${planSteps} step${planSteps === 1 ? "" : "s"}`,
          }
        : { state: "pending", detail: "No plan reported" },
    work: failed
      ? { state: "failed", detail: "Stopped with an error" }
      : partial
        ? { state: "blocked", detail: "Stopped before finishing" }
        : waitingFirstResponse
          ? { state: "waiting", detail: "Sent — waiting for the first response" }
          : executing
            ? { state: "active", detail: "Executing" }
            : streaming
              ? { state: "active", detail: "Responding" }
              : turnReplied || delivered
                ? { state: "complete", detail: "Replied" }
                : { state: "pending", detail: "Not started" },
    artifact:
      artifactCount > 0
        ? { state: "available", detail: `${artifactCount} output${artifactCount === 1 ? "" : "s"} ready` }
        : { state: "pending", detail: "None yet" },
    approval:
      runtimeState === "needs_approval"
        ? { state: "approval", detail: "Waiting for your decision" }
        : runtimeState === "blocked"
          ? { state: "blocked", detail: "Queued for an approver" }
          : approvalResolved
            ? { state: "complete", detail: "Resolved" }
            : { state: "not_needed", detail: "Not requested" },
    result: failed
      ? { state: "failed", detail: "Did not complete" }
      : partial
        ? { state: "blocked", detail: "Partly completed" }
        : approvalOpen
          ? { state: "waiting", detail: "After the approval" }
          : delivered
            ? { state: "available", detail: executionResult?.title?.trim() || "Delivered" }
            : working
              ? { state: "waiting", detail: "In progress" }
              : turnReplied && (runtimeState === "completed" || runtimeState === "idle")
                ? { state: "available", detail: "Answer ready" }
                : { state: "pending", detail: "Not yet" },
  }

  return MISSION_STAGE_ORDER.map((stage) => ({ id: stage.id, label: stage.label, ...stages[stage.id] }))
}

const STATE_UI: Record<MissionStageState, { label: string; icon: LucideIcon; marker: string; text: string; spin?: boolean }> = {
  complete: {
    label: "Complete",
    icon: Check,
    marker: "bg-[color:var(--g-text-primary)] text-background border-[color:var(--g-text-primary)]",
    text: "text-muted-foreground",
  },
  active: {
    label: "Active",
    icon: Loader2,
    marker: "bg-[color:var(--g-brand)] text-white border-[color:var(--g-brand)]",
    text: "text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
    spin: true,
  },
  waiting: {
    label: "Waiting",
    icon: Clock,
    marker: "bg-background text-[color:var(--g-brand-active)] border-[color:var(--g-brand)] dark:text-[color:var(--g-brand)]",
    text: "text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
  },
  pending: {
    label: "Not started",
    icon: Circle,
    marker: "bg-background text-transparent border-[color:var(--g-border-strong)]",
    text: "text-muted-foreground",
  },
  blocked: {
    label: "Blocked",
    icon: Ban,
    marker: "bg-destructive/10 text-destructive border-destructive",
    text: "text-destructive",
  },
  approval: {
    label: "Approval required",
    icon: Hand,
    marker: "bg-warning text-[color:var(--g-text-primary)] border-warning",
    text: "text-foreground",
  },
  available: {
    label: "Result available",
    icon: PackageCheck,
    marker: "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)] border-[color:var(--g-brand)] dark:text-[color:var(--g-brand)]",
    text: "text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
  },
  failed: {
    label: "Failed",
    icon: X,
    marker: "bg-destructive text-white border-destructive",
    text: "text-destructive",
  },
  not_needed: {
    label: "Not needed",
    icon: Minus,
    marker: "bg-transparent text-muted-foreground border-dashed border-[color:var(--g-border-default)]",
    text: "text-muted-foreground",
  },
}

function StageMarker({ state, size }: { state: MissionStageState; size: "sm" | "md" }) {
  const ui = STATE_UI[state]
  const Icon = ui.icon
  return (
    <span
      aria-hidden
      data-mission-marker={state}
      className={cn(
        "relative z-10 flex shrink-0 items-center justify-center rounded-full border",
        size === "md" ? "size-[18px]" : "size-3.5",
        ui.marker,
      )}
    >
      <Icon
        className={cn(size === "md" ? "size-[11px]" : "size-2", ui.spin && "animate-spin motion-reduce:animate-none")}
        strokeWidth={2.75}
      />
    </span>
  )
}

/** Vertical mission rail beside the work (desktop); a compact stage strip on narrow widths. */
export function AiMissionSpine({ stages, className }: { stages: MissionStage[]; className?: string }) {
  const focus = stages.find((stage) => ["approval", "blocked", "failed", "active", "waiting"].includes(stage.state))
  return (
    <>
      <ol
        aria-label="Request progress"
        data-gravitre-ai-mission=""
        className={cn("flex shrink-0 items-center gap-3 overflow-x-auto border-b border-divide px-3 py-2 lg:hidden", className)}
      >
        {stages.map((stage) => (
          <li key={stage.id} data-mission-stage={stage.id} data-state={stage.state} className="flex shrink-0 items-center gap-1.5 text-[11.5px]">
            <StageMarker state={stage.state} size="sm" />
            <span className={cn(stage.state === "pending" || stage.state === "not_needed" ? "text-muted-foreground" : "text-foreground")}>
              {stage.label}
            </span>
            <span className="sr-only">: {STATE_UI[stage.state].label}</span>
          </li>
        ))}
      </ol>
      <aside
        aria-label="Request progress"
        data-gravitre-ai-mission-rail=""
        className="hidden w-[240px] shrink-0 flex-col overflow-y-auto border-r border-divide bg-[color:var(--g-rail-bg)] lg:flex"
      >
        {focus ? (
          <p className="border-b border-divide px-4 py-2.5 text-[12px] text-foreground" aria-live="polite">
            <span className={cn("font-semibold", STATE_UI[focus.state].text)}>{STATE_UI[focus.state].label}</span>
            <span className="text-muted-foreground"> · {focus.label}</span>
          </p>
        ) : null}
        <ol className="relative flex flex-col px-4 py-4">
          {stages.map((stage, index) => {
            const ui = STATE_UI[stage.state]
            const quiet = stage.state === "pending" || stage.state === "not_needed"
            return (
              <li key={stage.id} data-mission-stage={stage.id} data-state={stage.state} className="relative flex gap-3 pb-5 last:pb-0">
                {index < stages.length - 1 ? (
                  <span
                    aria-hidden
                    className={cn(
                      "absolute left-[8.5px] top-[18px] h-[calc(100%-18px)] w-px",
                      stage.state === "complete" ? "bg-[color:var(--g-text-primary)]/60" : "bg-[color:var(--g-border-default)]",
                    )}
                  />
                ) : null}
                <StageMarker state={stage.state} size="md" />
                <div className="min-w-0 flex-1">
                  <p className="flex items-baseline justify-between gap-2">
                    <span className={cn("text-[12.5px] font-semibold", quiet ? "text-muted-foreground" : "text-foreground")}>
                      {stage.label}
                    </span>
                    <span className={cn("shrink-0 text-[11px] font-medium", ui.text)}>{ui.label}</span>
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
            )
          })}
        </ol>
      </aside>
    </>
  )
}
