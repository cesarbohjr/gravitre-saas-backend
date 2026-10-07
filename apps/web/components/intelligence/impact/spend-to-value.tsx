"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import { Sparkle } from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import { CertaintyMarker } from "@/components/intelligence/impact/certainty"
import {
  formatCount,
  formatHours,
  formatMultiple,
  formatUsd,
  returnMissingReason,
  type Certainty,
  type ImpactTotals,
} from "@/components/intelligence/impact/impact-model"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

type FlowCard = {
  label: string
  value: string
  certainty: Certainty
  hint: ReactNode
}

export function SpendToValueFlow({
  totals,
  loading,
  runningNow,
}: {
  totals: ImpactTotals
  loading: boolean
  /** Live workflow runs from the intelligence snapshot; null when unknown. */
  runningNow: number | null
}) {
  const show = (v: string) => (loading ? "…" : v)
  const cards: FlowCard[] = [
    {
      label: "Spent",
      value: show(formatUsd(totals.spent)),
      certainty: totals.spentCertainty,
      hint: "Model calls, all agents",
    },
    {
      label: "Tasks done",
      value: show(formatCount(totals.tasks)),
      certainty: totals.tasksCertainty,
      hint: runningNow != null ? `${formatCount(runningNow)} running now` : "Finished agent work",
    },
    {
      label: "Time saved",
      value: show(formatHours(totals.hours)),
      certainty: totals.hoursCertainty,
      hint: "Estimated from task type",
    },
    {
      label: "Revenue influenced",
      value: show(formatUsd(totals.revenue)),
      certainty: totals.revenueCertainty,
      hint:
        totals.revenueCertainty === "none" && !loading ? (
          <Link
            href={APP_ROUTES.plays}
            className="text-[color:var(--g-brand-active)] underline underline-offset-2 hover:text-[color:var(--g-brand-hover)] dark:text-[color:var(--g-brand)]"
          >
            Turn on revenue tracking
          </Link>
        ) : (
          "Verified deal values only"
        ),
    },
    {
      label: "Return",
      value: show(formatMultiple(totals.roi)),
      certainty: totals.roiCertainty,
      hint: totals.roi == null ? returnMissingReason(totals) : "Estimated labor value ÷ cost",
    },
  ]

  return (
    <section
      aria-labelledby="impact-flow-heading"
      className="rounded-[18px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4 sm:p-6"
    >
      <h2 id="impact-flow-heading" className={cn(TYPE.cardTitle, "text-lg")}>
        From spend to value
      </h2>
      <p className={cn(TYPE.bodyMuted, "mt-1")}>
        Read left to right: what Gravitre cost, the work it did, and what that work was worth.
      </p>

      <ol className="mt-[18px] grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:gap-5">
        {cards.map((card, i) => (
          <li key={card.label} className="relative flex min-w-0">
            <div
              className={cn(
                "flex min-h-[7.5rem] w-full flex-col gap-2 rounded-[14px] border p-4",
                card.certainty === "none"
                  ? "border-dashed border-[color:var(--g-border-strong)]"
                  : "border-[color:var(--g-border-default)]",
              )}
            >
              <span className="flex items-center justify-between gap-2 text-[13px] text-[color:var(--g-text-secondary)]">
                {card.label}
                <CertaintyMarker certainty={card.certainty} />
              </span>
              <span
                className={cn(
                  "text-[28px] font-semibold leading-none tabular-nums tracking-[-0.02em]",
                  card.certainty === "none"
                    ? "text-[color:var(--g-text-muted)]"
                    : "text-[color:var(--g-text-primary)]",
                )}
              >
                {card.value}
              </span>
              <span className={cn(TYPE.meta, "mt-auto")}>{card.hint}</span>
            </div>
            {i < cards.length - 1 ? (
              <span
                aria-hidden
                className="absolute -right-5 top-1/2 hidden w-5 -translate-y-1/2 text-center text-xs text-[color:var(--g-text-muted)] lg:block"
              >
                →
              </span>
            ) : null}
          </li>
        ))}
      </ol>

      {!loading ? <ExplanationCallout totals={totals} /> : null}
    </section>
  )
}

function ExplanationCallout({ totals }: { totals: ImpactTotals }) {
  const spent = totals.spent ?? 0
  const noTasks = !totals.tasks
  const unassigned = totals.unassignedCost

  let text: string | null = null
  let action: { label: string; href: string } | null = null

  if (unassigned > 0) {
    const share =
      unassigned >= spent - 0.000001
        ? `All ${formatUsd(unassigned)} came from work with no agent assigned`
        : `${formatUsd(unassigned)} of ${formatUsd(spent)} came from work with no agent assigned`
    text = noTasks
      ? `${share}, and no agent finished a task, so there is nothing to value yet. Assigning it lets Gravitre credit the work to the right team.`
      : `${share}. Assigning it lets Gravitre credit the work to the right team.`
    action = { label: "Assign to an agent", href: APP_ROUTES.workflows }
  } else if (spent > 0 && noTasks) {
    text = `${formatUsd(spent)} was spent but no agent finished a task, so there is nothing to value yet.`
    action = { label: "Open agents", href: APP_ROUTES.agents }
  }

  if (!text || !action) return null

  return (
    <div className="mt-[18px] flex flex-col gap-3 rounded-[12px] border border-[color:var(--g-warning)]/40 bg-[color:var(--g-approval-surface)] px-4 py-3.5 sm:flex-row sm:items-center">
      <Sparkle className="h-[18px] w-[18px] shrink-0 text-[color:var(--g-warning)]" weight="bold" aria-hidden />
      <p className="min-w-0 flex-1 text-[13.5px] leading-normal text-[color:var(--g-text-primary)]">{text}</p>
      <Button asChild className="h-9 shrink-0 self-start rounded-[10px] px-3.5 sm:self-auto">
        <Link href={action.href}>{action.label}</Link>
      </Button>
    </div>
  )
}
