"use client"

import Link from "next/link"
import { Check } from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import type { FirstResultStep } from "@/components/intelligence/impact/impact-model"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function FirstResultChecklist({ steps, loading }: { steps: FirstResultStep[]; loading: boolean }) {
  const done = steps.filter((s) => s.done).length
  const firstPending = steps.findIndex((s) => !s.done)
  const next = firstPending >= 0 ? steps[firstPending] : null

  return (
    <section
      aria-labelledby="impact-first-result-heading"
      className="rounded-[18px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id="impact-first-result-heading" className={cn(TYPE.cardTitle, "text-[15px]")}>
          Your first measured result
        </h2>
        <span className={TYPE.mono} aria-label={`${done} of ${steps.length} done`}>
          {loading ? "…" : `${done} / ${steps.length}`}
        </span>
      </div>

      <ol className="mt-3.5 space-y-2.5">
        {steps.map((step, i) => {
          const isNext = i === firstPending
          return (
            <li key={step.id} className="flex items-start gap-2.5">
              <span
                aria-hidden
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-[1.5px] text-xs font-semibold",
                  step.done
                    ? "border-[color:var(--g-brand)] bg-[color:var(--g-brand)] text-white"
                    : isNext
                      ? "border-[color:var(--g-danger)] text-[color:var(--g-danger)]"
                      : "border-[color:var(--g-border-strong)] text-[color:var(--g-text-secondary)]",
                )}
              >
                {step.done ? <Check className="h-3.5 w-3.5" weight="bold" /> : i + 1}
              </span>
              <span className="min-w-0">
                <Link
                  href={step.href}
                  className={cn(
                    "block text-[13.5px] font-medium hover:underline",
                    step.done ? "text-[color:var(--g-text-muted)] line-through" : "text-[color:var(--g-text-primary)]",
                  )}
                >
                  {step.title}
                  <span className="sr-only">{step.done ? " (done)" : " (to do)"}</span>
                </Link>
                <span className={cn(TYPE.meta, "mt-0.5 block")}>{step.detail}</span>
              </span>
            </li>
          )
        })}
      </ol>

      {next ? (
        <Button asChild variant="brand" className="mt-3.5 h-10 w-full rounded-[10px] text-[13.5px]">
          <Link href={next.href}>Start with step {firstPending + 1}</Link>
        </Button>
      ) : !loading ? (
        <p className={cn(TYPE.bodyMuted, "mt-3.5")}>All three are done. Measured results now fill in as agents work.</p>
      ) : null}
    </section>
  )
}
