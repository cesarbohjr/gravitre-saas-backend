"use client"

import { Database } from "@phosphor-icons/react"
import { readString } from "@/lib/intelligence/helpers"
import type { DecisionTransparencyEnvelope } from "@/lib/intelligence/visibility-types"

/** A 0–1 freshness score in words; the raw percentage meant nothing to users. */
function freshnessWords(score: number): string {
  if (score >= 0.75) return "recent"
  if (score >= 0.4) return "a few months old"
  return "older"
}

export function SourceIntelligencePanel({
  envelope,
  className,
}: {
  envelope?: DecisionTransparencyEnvelope | null
  className?: string
}) {
  const sources = envelope?.sources_used ?? envelope?.evidence_used ?? []
  if (!sources.length) {
    return (
      <div className={className}>
        <p className="text-xs text-muted-foreground">No sources were recorded for this answer.</p>
      </div>
    )
  }

  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-2">
        <Database className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
        <h4 className="text-sm font-medium text-foreground">Sources used</h4>
      </div>
      <ul className="space-y-2">
        {sources.slice(0, 8).map((row, index) => {
          const name = readString(row.name || row.label, "Source")
          const type = readString(row.type || row.kind, "document")
          const score = row.score ?? row.relevance
          const freshness = row.freshness_score
          return (
            <li
              key={`${name}-${index}`}
              className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-foreground">{name}</span>
                <span className="text-muted-foreground capitalize">{type}</span>
              </div>
              <div className="mt-1 flex flex-wrap gap-3 text-muted-foreground">
                {score != null && !Number.isNaN(Number(score)) ? (
                  <span>Relevance {Math.round(Number(score) * 100)}%</span>
                ) : null}
                {freshness != null && !Number.isNaN(Number(freshness)) ? (
                  <span>Freshness: {freshnessWords(Number(freshness))}</span>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
