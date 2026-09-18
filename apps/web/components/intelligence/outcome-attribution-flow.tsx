"use client"

/**
 * I7 — Interactive outcome attribution chain. Click a step to inspect evidence.
 */
import { useEffect, useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import type { OutcomeAttributionPath, OutcomePathStep } from "@/lib/api"
import { unknownStepCopy } from "@/lib/intelligence/performance-display"
import { qualityFlagToCopy } from "@/lib/intelligence/quality-copy"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function OutcomeAttributionFlow({
  paths,
  selectedPathId,
  onPathChange,
  className,
}: {
  paths: OutcomeAttributionPath[]
  selectedPathId?: string | null
  onPathChange?: (pathId: string) => void
  className?: string
}) {
  const reducedMotion = useReducedMotion()
  const active = paths.find((p) => p.id === selectedPathId) ?? paths[0]
  const [selectedKind, setSelectedKind] = useState<string | null>(null)

  useEffect(() => {
    setSelectedKind(null)
  }, [active?.id])

  if (!active) {
    return (
      <div
        className={cn(
          "rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/50 px-4 py-8 text-center",
          className,
        )}
      >
        <p className={TYPE.cardTitle}>No contributing stages</p>
        <p className={cn(TYPE.meta, "mt-1")}>{qualityFlagToCopy("NO_OUTCOME_ATTRIBUTION")}</p>
      </div>
    )
  }

  const selected = selectedKind
    ? active.steps.find((s) => s.kind === selectedKind)
    : undefined

  return (
    <section
      className={cn("bg-[color:var(--g-surface-1)]", className)}
      aria-labelledby="outcome-flow-heading"
    >
      <div className="flex flex-col gap-3 border-b border-divide pb-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p id="outcome-flow-heading" className={TYPE.eyebrow}>
            Contributing stages
          </p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Select a stage to inspect the span and evidence. Inspector stays closed until then.
          </p>
        </div>
        {paths.length > 1 ? (
          <label className="flex flex-col gap-0.5 sm:min-w-[12rem]">
            <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Scope
            </span>
            <select
              value={active.id}
              onChange={(e) => onPathChange?.(e.target.value)}
              className="h-8 rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 text-xs"
              aria-label="Attribution scope"
            >
              {paths.map((path) => (
                <option key={path.id} value={path.id}>
                  {path.scopeLabel}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className={TYPE.meta}>{active.scopeLabel}</p>
        )}
      </div>

      <div className={cn("grid gap-6 pt-4", selected && "lg:grid-cols-[minmax(0,1fr)_18rem]")}>
        <ol className="space-y-0">
          {active.steps.map((step, index) => {
            const selectedStep = step.kind === selected?.kind
            return (
              <li key={step.kind} className="relative flex gap-3">
                {index < active.steps.length - 1 ? (
                  <span
                    aria-hidden
                    className="absolute left-[13px] top-8 h-[calc(100%-8px)] w-px bg-divide"
                  />
                ) : null}
                <button
                  type="button"
                  onClick={() =>
                    setSelectedKind((prev) => (prev === step.kind ? null : step.kind))
                  }
                  aria-pressed={selectedStep}
                  className={cn(
                    "relative z-[1] mb-3 flex w-full items-start gap-3 rounded-[var(--np-radius-md)] border px-3 py-2.5 text-left transition-colors",
                    selectedStep
                      ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-intelligence-surface)]"
                      : "border-divide bg-[color:var(--g-surface-2)]/40 hover:border-[color:var(--g-brand-border)]",
                    !step.present && "opacity-80",
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                      step.present
                        ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className={TYPE.eyebrow}>{step.title}</span>
                    <span className="mt-0.5 block text-sm font-medium text-foreground">{step.label}</span>
                    {!step.present ? (
                      <span className={cn(TYPE.meta, "mt-0.5 block")}>{unknownStepCopy(step)}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            )
          })}
        </ol>

        {selected ? (
          <aside className="border border-[color:var(--g-border-active)] bg-[color:var(--g-surface-active)] p-4">
            <motion.div
              key={selected.kind}
              initial={reducedMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reducedMotion ? 0 : 0.2 }}
            >
              <StepInspector step={selected} />
            </motion.div>
          </aside>
        ) : (
          <p className={cn(TYPE.meta, "lg:col-span-2")}>
            Select a contributing stage — inspector stays closed until then.
          </p>
        )}
      </div>
    </section>
  )
}

function StepInspector({ step }: { step?: OutcomePathStep }) {
  if (!step) {
    return null
  }
  return (
    <div className="space-y-3">
      <div>
        <p className={TYPE.eyebrow}>Selected span</p>
        <p className="mt-1 text-sm font-medium text-foreground">{step.title}</p>
        <p className={cn(TYPE.meta, "mt-0.5")}>{step.label}</p>
      </div>
      {step.present && step.evidence.length > 0 ? (
        <ul className="space-y-1.5">
          {step.evidence.map((line) => (
            <li
              key={line}
              className="rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 py-1.5 text-xs text-muted-foreground"
            >
              {line}
            </li>
          ))}
        </ul>
      ) : (
        <p className={cn(TYPE.meta, "text-pretty")}>{unknownStepCopy(step)}</p>
      )}
      {step.sourceRecordId ? (
        <p className={TYPE.meta}>Record {step.sourceRecordId}</p>
      ) : null}
    </div>
  )
}
