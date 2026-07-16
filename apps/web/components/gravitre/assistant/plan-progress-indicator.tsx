"use client"

import { useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  AlertTriangle,
  Check,
  ChevronDown,
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

function shortStepLabel(description: string | undefined, index: number) {
  const text = description?.trim()
  if (!text) return `Step ${index + 1}`
  // Prefer a short lead phrase for the narrow stepper.
  const firstClause = text.split(/[.!:]/)[0]?.trim() ?? text
  return firstClause.length > 28 ? `${firstClause.slice(0, 27)}…` : firstClause
}

export function PlanProgressIndicator({ taskState }: { taskState: TaskState | null | undefined }) {
  // Collapsed by default so the plan never steals the chat canvas.
  const [expanded, setExpanded] = useState(false)
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
  const confidencePct =
    plan.confidence != null && Number.isFinite(plan.confidence)
      ? Math.round(plan.confidence * 100)
      : null
  const needsApproval = Boolean(plan.approvals_required?.length)
  const allDone = completedCount >= steps.length

  return (
    <div className="shrink-0 border-b border-border/60 bg-card/40 px-2 py-1.5 md:px-3">
      <div className="mx-auto w-full max-w-4xl">
        <div
          className={cn(
            "overflow-hidden rounded-xl border border-border/70 bg-card/90 shadow-sm backdrop-blur-sm",
            "ring-1 ring-emerald-500/5",
          )}
        >
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            aria-label={
              expanded
                ? "Collapse active plan"
                : `Expand active plan, step ${stepLabel} of ${steps.length}`
            }
            className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors hover:bg-muted/25 md:gap-3 md:px-3"
          >
            <span
              className={cn(
                "grid h-6 w-6 shrink-0 place-items-center rounded-md border",
                allDone
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "border-emerald-500/25 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300",
              )}
            >
              {allDone ? (
                <Check className="h-3.5 w-3.5" strokeWidth={2.5} aria-hidden />
              ) : (
                <ListChecks className="h-3.5 w-3.5" aria-hidden />
              )}
            </span>

            <div className="min-w-0 flex-1">
              <div className="mb-1 flex flex-wrap items-center gap-1.5">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Active plan
                </p>
                <span className="rounded bg-muted/70 px-1.5 py-px text-[10px] font-medium tabular-nums text-muted-foreground">
                  {allDone ? "Complete" : `${stepLabel}/${steps.length}`}
                </span>
                {needsApproval ? (
                  <span className="inline-flex items-center gap-0.5 rounded bg-amber-500/10 px-1.5 py-px text-[10px] font-medium text-amber-800 dark:text-amber-300">
                    <ShieldCheck className="h-3 w-3" aria-hidden />
                    Approval
                  </span>
                ) : null}
              </div>

              {/* Narrow horizontal stepper — brand emerald, reference-inspired */}
              <ol
                className="flex min-w-0 items-start gap-0 overflow-x-auto scrollbar-hide"
                aria-label={`Plan progress: ${completedCount} of ${steps.length} steps complete`}
              >
                {steps.map((step, index) => {
                  const done = step.step_id ? completedIds.has(step.step_id) : index < completedCount
                  const current = !allDone && index === currentIndex
                  const isLast = index === steps.length - 1
                  return (
                    <li
                      key={stepKey(step, index)}
                      className={cn("flex min-w-0 items-start", !isLast && "flex-1")}
                    >
                      <div className="flex min-w-0 flex-col items-center gap-0.5">
                        <span
                          className={cn(
                            "grid h-5 w-5 shrink-0 place-items-center rounded-full border transition-colors",
                            done &&
                              "border-emerald-500 bg-emerald-500 text-white shadow-sm shadow-emerald-500/20",
                            current &&
                              "rounded-md border-emerald-500 bg-background text-emerald-600 ring-2 ring-emerald-500/20 dark:text-emerald-300",
                            !done &&
                              !current &&
                              "border-border bg-muted/40 text-muted-foreground/40",
                          )}
                          aria-current={current ? "step" : undefined}
                        >
                          {done ? (
                            <Check className="h-3 w-3" strokeWidth={3} aria-hidden />
                          ) : current ? (
                            <span className="h-1.5 w-1.5 rounded-sm bg-emerald-500" aria-hidden />
                          ) : (
                            <span className="h-1 w-1 rounded-sm bg-muted-foreground/30" aria-hidden />
                          )}
                        </span>
                        <span
                          className={cn(
                            "hidden max-w-[5.5rem] truncate text-center text-[9px] leading-tight sm:block",
                            done && "text-muted-foreground/70",
                            current && "font-semibold text-foreground",
                            !done && !current && "text-muted-foreground/50",
                          )}
                        >
                          {shortStepLabel(step.description, index)}
                        </span>
                      </div>
                      {!isLast ? (
                        <span
                          aria-hidden
                          className={cn(
                            "mx-1 mt-2.5 h-px min-w-[12px] flex-1",
                            // Line after a completed step (or leading into/past current) uses brand emerald.
                            done || index < currentIndex ? "bg-emerald-500/70" : "bg-border",
                          )}
                        />
                      ) : null}
                    </li>
                  )
                })}
              </ol>

              <p className="mt-1 truncate text-[11px] text-muted-foreground sm:hidden">
                {allDone
                  ? "Plan finished"
                  : currentStep?.description || "Working the next step"}
              </p>
            </div>

            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200",
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
                transition={reduced ? { duration: 0.12 } : { duration: 0.2, ease: [0.2, 0, 0, 1] }}
                className="overflow-hidden"
              >
                <div className="space-y-2.5 border-t border-border/60 px-3 pb-3 pt-2.5">
                  {plan.goal ? (
                    <p className="rounded-lg bg-muted/35 px-2.5 py-1.5 text-xs leading-relaxed text-muted-foreground">
                      <span className="font-medium text-foreground/80">Goal</span>
                      <span className="mt-0.5 block">{plan.goal}</span>
                    </p>
                  ) : null}

                  {confidencePct != null ? (
                    <p className="text-[11px] text-muted-foreground">{confidencePct}% confidence</p>
                  ) : null}

                  <ol className="space-y-2">
                    {steps.map((step, index) => {
                      const done = step.step_id ? completedIds.has(step.step_id) : index < completedCount
                      const current = !allDone && index === currentIndex
                      return (
                        <li key={stepKey(step, index)} className="flex gap-2.5">
                          <span
                            className={cn(
                              "mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full border",
                              done && "border-emerald-500 bg-emerald-500 text-white",
                              current && "border-emerald-500 text-emerald-600",
                              !done && !current && "border-border text-muted-foreground/40",
                            )}
                          >
                            {done ? (
                              <Check className="h-2.5 w-2.5" strokeWidth={3} aria-hidden />
                            ) : current ? (
                              <span className="h-1.5 w-1.5 rounded-sm bg-emerald-500" aria-hidden />
                            ) : null}
                          </span>
                          <div className="min-w-0">
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
                              <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
                                In progress
                              </p>
                            ) : null}
                          </div>
                        </li>
                      )
                    })}
                  </ol>

                  {plan.risks?.length ? (
                    <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-2.5 py-2">
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-amber-900 dark:text-amber-200">
                        Risks
                      </p>
                      <ul className="space-y-1">
                        {plan.risks.slice(0, 4).map((risk) => (
                          <li
                            key={risk.title ?? risk.summary}
                            className="flex items-start gap-1.5 text-xs text-amber-900/90 dark:text-amber-200/90"
                          >
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
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
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
