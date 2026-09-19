"use client"

import { useState } from "react"
import Link from "next/link"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { LearningInsightDisplay } from "@/lib/intelligence/learning-insight-display"
import { buildLearningInsightMapHref } from "@/lib/intelligence/learning-map-focus"
import { MapTrifold } from "@phosphor-icons/react"

export function LearningInsightInspector({ insight }: { insight: LearningInsightDisplay }) {
  const mapHref = buildLearningInsightMapHref(insight.id)
  return (
    <div className="space-y-4 p-4" data-review-surface="learning-inspect">
      <div>
        <p className={TYPE.eyebrow}>Insight</p>
        <h2 className="mt-1 text-base font-medium leading-snug text-foreground">{insight.statement}</h2>
        {insight.learnedAtLabel ? (
          <p className={cn(TYPE.meta, "mt-1")}>Learned {insight.learnedAtLabel}</p>
        ) : null}
      </div>
      {insight.learnedFrom.length > 0 ? (
        <div>
          <p className={TYPE.eyebrow}>Learned from</p>
          <p className="mt-1 text-sm text-muted-foreground">{insight.learnedFrom.join(" · ")}</p>
        </div>
      ) : null}
      {insight.evidence.length > 0 ? (
        <div>
          <p className={TYPE.eyebrow}>Evidence</p>
          <ul className="mt-1 space-y-1">
            {insight.evidence.map((line) => (
              <li key={line} className="border-b border-divide py-1.5 text-xs text-muted-foreground last:border-b-0">
                {line}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {insight.affectedEntities.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          <span className={TYPE.eyebrow}>Entities: </span>
          {insight.affectedEntities.join(", ")}
        </p>
      ) : null}
      {insight.resultingChanges.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          <span className={TYPE.eyebrow}>Changes: </span>
          {insight.resultingChanges.join("; ")}
        </p>
      ) : null}
      {insight.provenance ? (
        <p className={cn(TYPE.meta, "border-t border-divide pt-2")}>Source: {insight.provenance}</p>
      ) : null}
      <Link
        href={mapHref}
        data-testid="learning-insight-map-link"
        data-review-cta="view-on-map"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand)] hover:underline"
      >
        <MapTrifold className="h-3.5 w-3.5" aria-hidden />
        View on intelligence map
      </Link>
    </div>
  )
}

/** @deprecated Use LearningInsightsList — kept so existing imports compile during migrate. */
export function LearningInsightCard({ insight }: { insight: LearningInsightDisplay }) {
  return <LearningInsightInspector insight={insight} />
}

export function LearningInsightsList({ insights }: { insights: LearningInsightDisplay[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = insights.find((insight) => insight.id === selectedId) ?? null

  return (
    <div className="flex flex-col border border-divide lg:flex-row">
      <ul className="min-w-0 flex-1 divide-y divide-divide" data-review-surface="learning-queue">
        {insights.map((insight) => {
          const isSelected = selectedId === insight.id
          return (
            <li key={insight.id}>
              <button
                type="button"
                data-testid="learning-insight-row"
                onClick={() => setSelectedId(insight.id)}
                className={cn(
                  "flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left transition",
                  isSelected
                    ? "bg-[color:var(--g-surface-2)]"
                    : "hover:bg-[color:var(--g-surface-2)]/50",
                )}
              >
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-foreground">{insight.statement}</span>
                  <span className={cn(TYPE.meta, "mt-0.5 block")}>
                    {insight.learnedAtLabel
                      ? `Learned ${insight.learnedAtLabel}`
                      : insight.provenance || "Select to inspect"}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {selected ? (
        <div className="flex-1 border-t border-divide bg-[color:var(--g-canvas)] lg:border-t-0 lg:border-l">
          <LearningInsightInspector insight={selected} />
        </div>
      ) : (
        <p className="sr-only">Select an insight — inspector stays closed until then.</p>
      )}
    </div>
  )
}
