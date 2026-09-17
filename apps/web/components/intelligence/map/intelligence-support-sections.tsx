"use client"

import Link from "next/link"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { HeuristicSuggestionCards } from "@/components/intelligence/heuristic-suggestion-cards"
import { TYPE } from "@/lib/design-system"
import { readString } from "@/lib/intelligence/helpers"
import { cn } from "@/lib/utils"
import { APP_ROUTES } from "@/lib/app-routes"
import { buildLearningInsightMapHref } from "@/lib/intelligence/learning-map-focus"
import { ArrowRight, Warning } from "@phosphor-icons/react"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

type BusinessSignalRow = Record<string, unknown>

export function WhatNeedsAttentionCompact({
  signals,
  isLoading,
  onSelectSignal,
  className,
}: {
  signals: BusinessSignalRow[] | null | undefined
  isLoading?: boolean
  onSelectSignal?: (signal: BusinessSignalRow) => void
  className?: string
}) {
  const top = [...(signals ?? [])]
    .sort((a, b) => Number(b.quality_score ?? 0) - Number(a.quality_score ?? 0))
    .slice(0, 3)

  return (
    <section className={cn("space-y-3", className)} aria-labelledby="needs-attention-heading">
      <div>
        <p className={TYPE.eyebrow}>Contextual</p>
        <h2 id="needs-attention-heading" className={TYPE.sectionTitle}>
          What needs attention
        </h2>
      </div>
      {isLoading && !signals ? (
        <p className={TYPE.meta}>Loading signals…</p>
      ) : top.length === 0 ? (
        <p className={cn(TYPE.bodyMuted, "rounded-md border border-dashed border-divide px-4 py-3")}>
          Nothing ranked as urgent — shown honestly as empty.
        </p>
      ) : (
        <ul className="grid gap-2 md:grid-cols-3">
          {top.map((signal, index) => (
            <li key={readString(signal.id, String(index))}>
              <button
                type="button"
                onClick={() => onSelectSignal?.(signal)}
                className="flex h-full w-full flex-col rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-3 text-left transition-colors hover:border-amber-500/40 hover:bg-[color:var(--g-surface-2)]"
              >
                <Warning className="h-4 w-4 text-amber-600" weight="fill" aria-hidden />
                <span className={cn(TYPE.cardTitle, "mt-2 line-clamp-2")}>
                  {readString(signal.title, "Business signal")}
                </span>
                <span className={cn(TYPE.meta, "mt-1 line-clamp-2")}>
                  {readString(signal.summary, "")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function BusinessImpactCompact({
  totalEvents,
  avgConfidence,
  className,
}: {
  totalEvents: number
  avgConfidence: number | null | undefined
  className?: string
}) {
  return (
    <section className={cn("space-y-3", className)} aria-labelledby="business-impact-heading">
      <div>
        <p className={TYPE.eyebrow}>Measured</p>
        <h2 id="business-impact-heading" className={TYPE.sectionTitle}>
          Business impact
        </h2>
      </div>
      <div className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-3">
        <GravitreMetric
          label="Outcome events"
          value={totalEvents}
          hint="Last 7 days"
          icon={<NucleoIntelligence className="h-4 w-4" />}
        />
        <GravitreMetric
          label="Avg confidence"
          value={avgConfidence != null ? `${Math.round(avgConfidence * 100)}%` : "—"}
          hint="Trust period"
        />
        <GravitreMetric
          label="Reports"
          value="Open"
          hint="Department scorecards"
          href={APP_ROUTES.intelligenceReports}
        />
      </div>
    </section>
  )
}

export function WhatGravitreLearnedSection({
  learnings,
  className,
}: {
  learnings?: Array<{ id: string; statement: string; learnedAt?: string; confidence?: string }>
  className?: string
}) {
  return (
    <section className={cn("space-y-3", className)} aria-labelledby="learned-heading">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className={TYPE.eyebrow}>Patterns</p>
          <h2 id="learned-heading" className={TYPE.sectionTitle}>
            What Gravitre learned
          </h2>
        </div>
        <Link
          href={APP_ROUTES.learning}
          className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Full learning hub
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      </div>
      {learnings && learnings.length > 0 ? (
        <ul className="grid gap-2 md:grid-cols-3">
          {learnings.map((row) => (
            <li
              key={row.id}
              className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-3"
            >
              <p className={cn(TYPE.cardTitle, "line-clamp-3")}>{row.statement}</p>
              {row.learnedAt ? (
                <p className={cn(TYPE.meta, "mt-1")}>Learned {row.learnedAt}</p>
              ) : null}
              {row.id ? (
                <Link
                  href={buildLearningInsightMapHref(row.id)}
                  className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-[color:var(--g-brand)] hover:underline"
                  data-testid="overview-learning-map-link"
                >
                  View on intelligence map
                  <ArrowRight className="h-3 w-3" aria-hidden />
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className={cn(TYPE.bodyMuted, "rounded-md border border-dashed border-divide px-4 py-3")}>
          No validated business learning in canonical state yet — not model readiness or platform
          telemetry.
        </p>
      )}
      <HeuristicSuggestionCards />
    </section>
  )
}
