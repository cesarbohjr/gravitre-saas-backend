"use client"

import { useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Circle,
  ListChecks,
  ShieldCheck,
} from "lucide-react"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

type PlanStep = {
  step_id?: string
  description?: string
}

type PlanRisk = {
  title?: string
  summary?: string
  severity?: string
}

type StrategicPlan = {
  goal?: string
  steps?: PlanStep[]
  risks?: PlanRisk[]
  confidence?: number
  approvals_required?: string[]
}

type TaskState = {
  current_plan?: StrategicPlan | null
  completed_steps?: PlanStep[]
  pending_steps?: PlanStep[]
}

function stepKey(step: PlanStep, index: number) {
  return step.step_id ?? `step-${index}-${step.description ?? ""}`
}

export function PlanProgressIndicator({ taskState }: { taskState: TaskState | null | undefined }) {
  const [expanded, setExpanded] = useState(true)
  const { reduced } = useMotionPrefs()

  const plan = taskState?.current_plan
  const steps = plan?.steps ?? []

  const { completedIds, completedCount, currentIndex, currentStep } = useMemo(() => {
    const completed = new Set(
      (taskState?.completed_steps ?? []).map((step) => step.step_id).filter(Boolean) as string[],
    )
    const doneCount = steps.filter((step) => step.step_id && completed.has(step.step_id)).length
    const pendingFirst = (taskState?.pending_steps ?? [])[0]
    const fallbackIndex = steps.findIndex((step) => !(step.step_id && completed.has(step.step_id)))
    const activeIndex =
      pendingFirst?.step_id != null
        ? Math.max(
            0,
            steps.findIndex((step) => step.step_id === pendingFirst.step_id),
          )
        : fallbackIndex >= 0
          ? fallbackIndex
          : Math.min(doneCount, Math.max(steps.length - 1, 0))
    const activeStep =
      pendingFirst ??
      (activeIndex >= 0 ? steps[activeIndex] : undefined) ??
      steps[Math.min(doneCount, steps.length - 1)]

    return {
      completedIds: completed,
      completedCount: doneCount,
      currentIndex: activeIndex >= 0 ? activeIndex : 0,
      currentStep: activeStep,
    }
  }, [steps, taskState?.completed_steps, taskState?.pending_steps])

  if (!plan?.steps?.length) return null

  const stepLabel = Math.min(completedCount + 1, steps.length)
  const progressRatio = steps.length ? completedCount / steps.length : 0
  const confidencePct =
    plan.confidence != null && Number.isFinite(plan.confidence)
      ? Math.round(plan.confidence * 100)
      : null
  const needsApproval = Boolean(plan.approvals_required?.length)
  const allDone = completedCount >= steps.length

  return (
    <div className="shrink-0 border-b border-border/70 bg-gradient-to-b from-muted/35 via-card/50 to-transparent px-3 py-2.5 md:px-5">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className={cn(
            "relative overflow-hidden rounded-2xl border border-border/70 bg-card/80 shadow-sm backdrop-blur-sm",
            "ring-1 ring-black/[0.02] dark:ring-white/[0.04]",
          )}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-foreground/15 to-transparent"
          />

          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            className="flex w-full items-start gap-3 px-3.5 py-3 text-left transition-colors hover:bg-muted/30"
          >
            <span
              className={cn(
                "mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl border",
                allDone
                  ? "border-success/30 bg-success/10 text-success"
                  : "border-border/80 bg-muted/50 text-foreground",
              )}
            >
              {allDone ? (
                <CheckCircle2 className="h-4 w-4" aria-hidden />
              ) : (
                <ListChecks className="h-4 w-4" aria-hidden />
              )}
            </span>

            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Active plan
                </p>
                <span className="rounded-md bg-muted/70 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
                  {allDone ? "Complete" : `Step ${stepLabel} of ${steps.length}`}
                </span>
                {confidencePct != null ? (
                  <span className="rounded-md bg-muted/50 px-1.5 py-0.5 text-[10px] tabular-nums text-muted-foreground">
                    {confidencePct}% confidence
                  </span>
                ) : null}
                {needsApproval ? (
                  <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 dark:text-amber-300">
                    <ShieldCheck className="h-3 w-3" aria-hidden />
                    Approval required
                  </span>
                ) : null}
              </div>

              <p className="truncate text-sm font-medium tracking-tight text-foreground">
                {allDone
                  ? "Plan finished — review results below"
                  : currentStep?.description || "Working the next step"}
              </p>

              {plan.goal ? (
                <p className="line-clamp-1 text-[11px] text-muted-foreground">
                  <span className="text-muted-foreground/80">Goal · </span>
                  {plan.goal}
                </p>
              ) : null}

              <div
                className="flex items-center gap-1.5 pt-0.5"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={steps.length}
                aria-valuenow={completedCount}
                aria-label={`Plan progress: ${completedCount} of ${steps.length} steps complete`}
              >
                {steps.map((step, index) => {
                  const done = step.step_id ? completedIds.has(step.step_id) : index < completedCount
                  const current = !allDone && index === currentIndex
                  return (
                    <div
                      key={stepKey(step, index)}
                      className={cn(
                        "h-1.5 flex-1 rounded-full transition-colors",
                        done && "bg-success/80",
                        current && "bg-foreground/80",
                        !done && !current && "bg-muted-foreground/15",
                      )}
                    />
                  )
                })}
              </div>
            </div>

            <ChevronDown
              className={cn(
                "mt-2 h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
                expanded && "rotate-180",
              )}
              aria-hidden
            />
          </button>

          <AnimatePresence initial={false}>
            {expanded ? (
              <motion.div
                key="plan-details"
                initial={reduced ? false : { height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
                transition={reduced ? { duration: 0.12 } : { duration: 0.22, ease: [0.2, 0, 0, 1] }}
                className="overflow-hidden"
              >
                <div className="space-y-3 border-t border-border/60 px-3.5 pb-3.5 pt-3">
                  {plan.goal ? (
                    <p className="rounded-xl bg-muted/35 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
                      <span className="font-medium text-foreground/80">Goal</span>
                      <span className="mt-0.5 block text-muted-foreground">{plan.goal}</span>
                    </p>
                  ) : null}

                  <ol className="relative space-y-0">
                    {steps.map((step, index) => {
                      const done = step.step_id ? completedIds.has(step.step_id) : index < completedCount
                      const current = !allDone && index === currentIndex
                      const isLast = index === steps.length - 1
                      return (
                        <li key={stepKey(step, index)} className="relative flex gap-3 pb-3 last:pb-0">
                          {!isLast ? (
                            <span
                              aria-hidden
                              className={cn(
                                "absolute left-[9px] top-5 h-[calc(100%-8px)] w-px",
                                done ? "bg-success/40" : "bg-border",
                              )}
                            />
                          ) : null}
                          <span
                            className={cn(
                              "relative z-[1] mt-0.5 grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full border bg-card",
                              done && "border-success/40 text-success",
                              current && "border-foreground text-foreground ring-2 ring-foreground/10",
                              !done && !current && "border-border text-muted-foreground/50",
                            )}
                          >
                            {done ? (
                              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                            ) : (
                              <Circle
                                className={cn("h-2.5 w-2.5", current && "fill-foreground")}
                                aria-hidden
                              />
                            )}
                          </span>
                          <div className="min-w-0 pt-px">
                            <p
                              className={cn(
                                "text-xs leading-snug",
                                done && "text-muted-foreground/70 line-through",
                                current && "font-medium text-foreground",
                                !done && !current && "text-muted-foreground",
                              )}
                            >
                              {step.description}
                            </p>
                            {current ? (
                              <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                                In progress
                              </p>
                            ) : null}
                          </div>
                        </li>
                      )
                    })}
                  </ol>

                  {plan.risks?.length ? (
                    <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2.5">
                      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-amber-900 dark:text-amber-200">
                        Risks
                      </p>
                      <ul className="space-y-1.5">
                        {plan.risks.slice(0, 4).map((risk) => (
                          <li
                            key={risk.title ?? risk.summary}
                            className="flex items-start gap-2 text-xs text-amber-900/90 dark:text-amber-200/90"
                          >
                            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                            <span>
                              {risk.title ? <span className="font-medium">{risk.title}</span> : null}
                              {risk.summary ? (
                                <span className={risk.title ? " text-amber-800/80 dark:text-amber-200/70" : undefined}>
                                  {risk.title ? `: ${risk.summary}` : risk.summary}
                                </span>
                              ) : null}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {progressRatio > 0 && !allDone ? (
                    <p className="text-[11px] text-muted-foreground">
                      {completedCount} of {steps.length} steps complete
                      {needsApproval ? " · execution waits for your approval" : ""}
                    </p>
                  ) : null}
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
