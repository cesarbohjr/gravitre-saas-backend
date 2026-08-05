/**
 * Progress UX v2 — persistent task side panel for multi-step Chat work.
 *
 * Appears only when planned/executed steps >= SIDE_PANEL_STEP_THRESHOLD (Phase 0
 * telemetry: 96% of recorded chat tasks are 1-2 steps). The panel is ADDITIVE —
 * it never replaces the inline BusinessOutcome card in the transcript.
 *
 * Data sources (no new stores):
 *   Progress — SSE progressSteps / pendingTask.params.steps via deriveNamedProgressSteps
 *   Outputs  — businessOutcomesApi filtered by conversationId (same as Activity) + hosted files
 *   Context  — contextExplanation + pendingTask connector/action params
 */
"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { CaretDown, CheckCircle, Circle, ArrowSquareOut } from "@phosphor-icons/react"
import { Loader2 } from "lucide-react"
import { businessOutcomesApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import type { ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { BusinessOutcomeDto } from "@/components/gravitre/business-outcome/business-outcome-view"
import {
  FileReferenceChip,
  type HostedFileRef,
} from "@/components/gravitre/assistant/file-reference-chip"
import {
  deriveNamedProgressSteps,
  formatStepCounter,
  type NamedProgressStep,
} from "@/lib/chat-progress-steps"
import {
  countPlannedOrExecutedSteps,
  shouldShowTaskSidePanel,
  SIDE_PANEL_STEP_THRESHOLD,
} from "@/lib/task-side-panel-threshold"

export { shouldShowTaskSidePanel, SIDE_PANEL_STEP_THRESHOLD }

type TaskSidePanelProps = {
  conversationId?: string | null
  progressSteps?: string[] | null
  pendingTask?: ChatPendingTask | null
  contextExplanation?: string | null
  /** Hosted files produced by this task, if any. Rendered in Outputs. */
  hostedFiles?: HostedFileRef[]
  className?: string
}

/** Collapsible section shell. Sections stay open by default. */
function PanelSection({
  title,
  meta,
  action,
  children,
}: {
  title: string
  meta?: string | null
  action?: React.ReactNode
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  const sectionId = `task-panel-${title.toLowerCase()}`

  return (
    <section className="rounded-lg border border-border/60 bg-background/40">
      <div className="flex items-center gap-1.5 px-3 py-2.5">
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          aria-expanded={open}
          aria-controls={sectionId}
          className="group -ml-1 flex min-w-0 flex-1 items-center gap-1.5 rounded px-1 py-0.5 text-left transition-colors hover:bg-muted/50"
        >
          <CaretDown
            className={cn(
              "h-3 w-3 shrink-0 text-muted-foreground transition-transform",
              !open && "-rotate-90",
            )}
            weight="bold"
            aria-hidden
          />
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            {title}
          </span>
          {meta ? (
            <span className="ml-auto truncate text-[11px] tabular-nums text-muted-foreground/80">
              {meta}
            </span>
          ) : null}
        </button>
        {action}
      </div>
      {open ? (
        <div id={sectionId} className="px-3 pb-3">
          {children}
        </div>
      ) : null}
    </section>
  )
}

function ProgressChecklist({ steps }: { steps: NamedProgressStep[] }) {
  if (steps.length === 0) {
    return <p className="text-xs text-muted-foreground">No steps yet for this task.</p>
  }

  return (
    <ol className="space-y-2">
      {steps.map((step, index) => (
        <li key={`${step.label}-${index}`} className="flex items-start gap-2 text-xs">
          <span className="mt-px flex h-4 w-4 shrink-0 items-center justify-center" aria-hidden>
            {step.status === "done" ? (
              <CheckCircle
                className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400"
                weight="fill"
              />
            ) : step.status === "current" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-600 dark:text-emerald-400" />
            ) : (
              <Circle className="h-3 w-3 text-muted-foreground/50" weight="bold" />
            )}
          </span>
          <span
            className={cn(
              "min-w-0 leading-relaxed",
              step.status === "current" && "font-medium text-foreground",
              step.status === "done" && "text-muted-foreground",
              step.status === "pending" && "text-muted-foreground/70",
            )}
          >
            {step.label}
          </span>
          <span className="sr-only">
            {step.status === "done"
              ? "(completed)"
              : step.status === "current"
                ? "(in progress)"
                : "(pending)"}
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
  hostedFiles,
  className,
}: TaskSidePanelProps) {
  const { user } = useAuth()
  const stepCount = countPlannedOrExecutedSteps(progressSteps, pendingTask)

  const steps = useMemo(
    () => deriveNamedProgressSteps(progressSteps, pendingTask),
    [progressSteps, pendingTask],
  )
  const stepCounter = formatStepCounter(steps) ?? `${stepCount} steps`

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

  const files = hostedFiles ?? []
  const outputCount = taskOutcomes.length + files.length

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
        "flex w-full flex-col gap-2 rounded-xl border border-border/70 bg-card/50 p-2 lg:w-[19rem] lg:shrink-0",
        className,
      )}
      aria-label="Task progress panel"
      data-testid="task-side-panel"
      data-step-count={stepCount}
    >
      <PanelSection title="Progress" meta={stepCounter}>
        <ProgressChecklist steps={steps} />
      </PanelSection>

      <PanelSection
        title="Outputs"
        meta={outputCount > 0 ? String(outputCount) : null}
        action={
          <Link
            href={APP_ROUTES.activity}
            className="inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
          >
            Activity
            <ArrowSquareOut className="h-3 w-3" aria-hidden />
          </Link>
        }
      >
        {outputCount === 0 ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Outputs for this task appear here and on the Activity page.
          </p>
        ) : (
          <div className="space-y-2">
            {taskOutcomes.slice(0, 5).map((outcome) => (
              <Link
                key={outcome.id}
                href={APP_ROUTES.activity}
                className="block rounded-lg border border-border/50 bg-background/60 px-2.5 py-2 text-xs transition-colors hover:border-border hover:bg-muted/40"
              >
                <p className="line-clamp-2 font-medium text-foreground">{outcome.title}</p>
                {outcome.sections?.summary ? (
                  <p className="mt-0.5 line-clamp-2 leading-relaxed text-muted-foreground">
                    {outcome.sections.summary}
                  </p>
                ) : null}
              </Link>
            ))}
            {files.map((file) => (
              <FileReferenceChip
                key={file.id || file.filename || file.download_url || JSON.stringify(file)}
                file={file}
              />
            ))}
          </div>
        )}
      </PanelSection>

      <PanelSection title="Context">
        {contextBits.length === 0 ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Connectors and tools appear here as they run.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {contextBits.map((bit) => (
              <li key={bit} className="text-xs leading-relaxed text-muted-foreground">
                {bit}
              </li>
            ))}
          </ul>
        )}
      </PanelSection>
    </aside>
  )
}
