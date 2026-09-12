"use client"

/**
 * Intelligence redesign, brief-Phase 3 (2026-09-11) — Overview Layer 2:
 * "What matters now." Real ranked signals from the business signals engine
 * (server-side quality_score ranking — see backend/app/services/
 * recommendation_quality_engine.py `rank_recommendations`). Never more than
 * a handful; never fabricated when the org has no signals yet.
 */

import Link from "next/link"
import useSWR from "swr"
import { assistantApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { readString } from "@/lib/intelligence/helpers"
import { cn } from "@/lib/utils"
import { ArrowRight, ChartLineUp, Warning } from "@phosphor-icons/react"

const MAX_SIGNALS = 5

type BusinessSignalRow = Record<string, unknown>

function signalScore(row: BusinessSignalRow): number | null {
  const raw = row.quality_score ?? row.confidence
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

export function useWhatMattersNow(enabled: boolean) {
  return useSWR(
    enabled ? "intelligence/overview/business-signals" : null,
    () => assistantApi.businessSignals(),
    { revalidateOnFocus: false, refreshInterval: 60_000 },
  )
}

export function WhatMattersNowPanel({
  signals,
  isLoading,
  className,
}: {
  signals: BusinessSignalRow[] | null | undefined
  isLoading?: boolean
  className?: string
}) {
  const ranked = [...(signals ?? [])].sort((a, b) => (signalScore(b) ?? 0) - (signalScore(a) ?? 0))
  const top = ranked.slice(0, MAX_SIGNALS)

  return (
    <section
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
      aria-labelledby="what-matters-now-heading"
      data-what-matters-now=""
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={TYPE.eyebrow}>Layer 2</p>
          <h2 id="what-matters-now-heading" className={TYPE.sectionTitle}>
            What matters now
          </h2>
          <p className={cn(TYPE.bodyMuted, "mt-1 max-w-2xl")}>
            Real signals ranked by quality score — never more than a handful, never invented when
            there&apos;s nothing to show.
          </p>
        </div>
      </div>

      {isLoading && !signals ? (
        <p className={cn(TYPE.meta, "mt-4")}>Loading signals…</p>
      ) : top.length === 0 ? (
        <div className="mt-4 rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)] px-4 py-6 text-center">
          <p className={TYPE.cardTitle}>Nothing ranked as urgent right now</p>
          <p className={cn(TYPE.meta, "mt-1")}>
            No qualifying business signals for this org yet — shown honestly as empty rather than a
            placeholder card.
          </p>
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {top.map((signal, index) => {
            const isRisk = signal.signal_type === "risk" || signal.signal_type === "alert"
            const Icon = isRisk ? Warning : ChartLineUp
            const score = signalScore(signal)
            const title = readString(signal.title, "Business signal")
            const summary = readString(signal.summary, "")
            return (
              <li
                key={readString(signal.id, String(index))}
                className="flex items-start gap-3 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2.5"
              >
                <span
                  className={cn(
                    "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                    isRisk
                      ? "bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]"
                      : "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" weight="duotone" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className={TYPE.cardTitle}>{title}</p>
                  {summary ? <p className={cn(TYPE.bodyMuted, "mt-0.5")}>{summary}</p> : null}
                  <p className={cn(TYPE.meta, "mt-1")}>
                    {score != null ? `${Math.round(score * 100)}% quality score` : "Quality score not available"}
                    {typeof signal.source === "string" ? ` · ${signal.source.replace(/_/g, " ")}` : ""}
                  </p>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <div className="mt-4 flex justify-end">
        <Link
          href="/ai?prompt=What%20needs%20attention%3F"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Ask Gravitre for more detail
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      </div>
    </section>
  )
}