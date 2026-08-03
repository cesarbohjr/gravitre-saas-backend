/**
 * Progress UX v2 — Cowork-style persistent side panel.
 * Appears only when planned/executed steps ≥ SIDE_PANEL_STEP_THRESHOLD (Phase 0 telemetry).
 * Reuses BusinessOutcome list + existing progressSteps / pendingTask — no new stores.
 */
"use client"

import { useMemo } from "react"
import useSWR from "swr"
import Link from "next/link"
import { CheckCircle2, Circle, ExternalLink, Loader2 } from "lucide-react"
import { businessOutcomesApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import type { ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { BusinessOutcomeDto } from "@/components/gravitre/business-outcome/business-outcome-view"

/** Evidence-based threshold from Phase 0 (96% of chat tasks are 1–2 steps). */
export const SIDE_PANEL_STEP_THRESHOLD = 3

type TaskSidePanelProps = {
  conversationId?: string | null
  progressSteps?: string[] | null
  pendingTask?: ChatPendingTask | null
  contextExplanation?: string | null
  className?: string
}

function countPlannedOrExecutedSteps(
  progressSteps: string[] | null | undefined,
  pendingTask: ChatPendingTask | null | undefined,
): number {
  const pendingCount = Array.isArray(pendingTask?.params?.steps)
    ? pendingTask!.params!.steps!.length
    : 0
  const fromProgress = (progressSteps ?? []).filter((step) =>
    /^(Running:|Completed:|Step \d+\/\d+:)/i.test(String(step).trim()),
  ).length
  return Math.max(pendingCount, fromProgress)
}

export function shouldShowTaskSidePanel(
  progressSteps: string[] | null | undefined,
  pendingTask: ChatPendingTask | null | undefined,
): boolean {
  return countPlannedOrExecutedSteps(progressSteps, pendingTask) >= SIDE_PANEL_STEP_THRESHOLD
}

function ProgressChecklist({
  progressSteps,
  pendingTask,
}: {
  progressSteps?: string[] | null
  pendingTask?: ChatPendingTask | null
}) {
  const items = useMemo(() => {
    const fromProgress = (progressSteps ?? [])
      .map((raw) => String(raw).trim())
      .filter(Boolean)
      .map((text) => {
        if (text.startsWith("Completed: ")) {
          return { text: text.slice("Completed: ".length), status: "done" as const }
        }
        if (text.startsWith("Running: ")) {
          return { text: text.slice("Running: ".length), status: "current" as const }
        }
        if (/^Step \d+\/\d+:/i.test(text)) {
          return { text, status: "pending" as const }
        }
        return { text, status: "pending" as const }
      })
    if (fromProgress.length > 0) return fromProgress

    const steps = pendingTask?.params?.steps
    if (!Array.isArray(steps)) return []
    const currentIdx = Number(pendingTask?.params?.current_step_index ?? -1)
    return steps.map((step, index) => {
      const label = String(step.label || `Step ${index + 1}`).trim()
      const status =
        currentIdx >= 0 && index < currentIdx
          ? ("done" as const)
          : currentIdx >= 0 && index === currentIdx
            ? ("current" as const)
            : ("pending" as const)
      return { text: label, status }
    })
  }, [progressSteps, pendingTask])

  if (items.length === 0) {
    return <p className="text-xs text-muted-foreground">No steps yet for this task.</p>
  }

  return (
    <ol className="space-y-1.5">
      {items.map((item, index) => (
        <li key={`${item.text}-${index}`} className="flex items-start gap-2 text-xs">
          {item.status === "done" ? (
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" aria-hidden />
          ) : item.status === "current" ? (
            <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-hidden />
          ) : (
            <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
          )}
          <span
            className={cn(
              item.status === "current" && "font-medium text-foreground",
              item.status === "done" && "text-muted-foreground",
              item.status === "pending" && "text-muted-foreground",
            )}
          >
            {item.text}
          </span>
        </li>
      ))}
    </ol>
  )
}

export function TaskSidePanel({
  conversationId,
  progressSteps,
  pendingTask,
  contextExplanation,
  className,
}: TaskSidePanelProps) {
  const { user } = useAuth()
  const stepCount = countPlannedOrExecutedSteps(progressSteps, pendingTask)

  const { data } = useSWR(
    user && conversationId ? ["task-side-panel-outcomes", conversationId] : null,
    () => businessOutcomesApi.list({ limit: 40 }),
    { revalidateOnFocus: false, refreshInterval: 8000 },
  )

  const taskOutcomes = useMemo(() => {
    const rows = (data?.businessOutcomes ?? []) as BusinessOutcomeDto[]
    if (!conversationId) return []
    return rows.filter((row) => String(row.conversationId || "") === conversationId)
  }, [data, conversationId])

  const contextBits = useMemo(() => {
    const bits: string[] = []
    if (contextExplanation?.trim()) bits.push(contextExplanation.trim())
    const integration = String(pendingTask?.params?.integration || "").trim()
    if (integration) bits.push(`Connector: ${integration}`)
    const action = String(pendingTask?.params?.invoke_action || pendingTask?.params?.label || "").trim()
    if (action && !action.includes(".")) bits.push(`Action: ${action}`)
    return bits
  }, [contextExplanation, pendingTask])

  return (
    <aside
      className={cn(
        "flex w-full flex-col gap-4 rounded-xl border border-border/70 bg-card/50 p-4 lg:w-72 lg:shrink-0",
        className,
      )}
      aria-label="Task progress panel"
    >
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Progress
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {stepCount} step{stepCount === 1 ? "" : "s"} · multi-step task
        </p>
        <div className="mt-3">
          <ProgressChecklist progressSteps={progressSteps} pendingTask={pendingTask} />
        </div>
      </div>

      <div className="border-t border-border/50 pt-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Outputs
          </p>
          <Link
            href={APP_ROUTES.activity}
            className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
          >
            Activity
            <ExternalLink className="h-3 w-3" aria-hidden />
          </Link>
        </div>
        {taskOutcomes.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Outputs for this task appear here and on the Activity page when available.
          </p>
        ) : (
          <ul className="space-y-2">
            {taskOutcomes.slice(0, 5).map((outcome) => (
              <li key={outcome.id}>
                <Link
                  href={APP_ROUTES.activity}
                  className="block rounded-md border border-border/50 px-2.5 py-2 text-xs hover:bg-muted/40"
                >
                  <p className="font-medium text-foreground line-clamp-2">{outcome.title}</p>
                  {outcome.sections?.summary ? (
                    <p className="mt-0.5 line-clamp-2 text-muted-foreground">
                      {outcome.sections.summary}
                    </p>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-border/50 pt-3">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Context
        </p>
        {contextBits.length === 0 ? (
          <p className="text-xs text-muted-foreground">Conversation context loads as tools run.</p>
        ) : (
          <ul className="space-y-1.5 text-xs text-muted-foreground">
            {contextBits.map((bit) => (
              <li key={bit}>{bit}</li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
