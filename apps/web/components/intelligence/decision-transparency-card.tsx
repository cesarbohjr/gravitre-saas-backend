"use client"

import { Badge } from "@/components/ui/badge"
import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"
import { LearningConfidenceBadge } from "@/components/intelligence/learning-confidence-badge"
import { readString } from "@/lib/intelligence/helpers"
import { freshnessLabelText } from "@/lib/intelligence/visibility-helpers"
import type { DecisionTransparencyEnvelope } from "@/lib/intelligence/visibility-types"

export function DecisionTransparencyCard({
  envelope,
  className,
}: {
  envelope?: DecisionTransparencyEnvelope | null
  className?: string
}) {
  if (!envelope) return null

  const alt = envelope.alternative_paths_considered
  const domain = envelope.domain_context ?? {}
  const gaps = envelope.known_gaps ?? envelope.missing_context ?? []
  const isEstimate = Boolean(
    envelope.confidence_is_estimate ?? envelope.confidenceIsEstimate,
  )
  const runtimeStatus = envelope.runtime_status?.trim()
  const confSource = envelope.confidence_source ?? envelope.confidenceSource

  return (
    <article className={`rounded-2xl border border-border/70 bg-card p-4 md:p-5 ${className ?? ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-foreground">Decision transparency</h3>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">
            Evidence-level visibility only — no internal reasoning or deliberation.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {runtimeStatus ? (
            <Badge
              variant="outline"
              className="border-sky-500/30 bg-sky-500/5 text-sky-900 dark:text-sky-200"
              title="Whether a trained artifact is loaded at runtime (not catalog TRAINED)."
            >
              {runtimeStatus === "heuristic" ? "Heuristic runtime" : runtimeStatus.replace(/_/g, " ")}
            </Badge>
          ) : null}
          <ConfidenceBadge score={envelope.confidence} isEstimate={isEstimate} />
        </div>
      </div>
      {confSource ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Confidence source: <span className="font-medium text-foreground">{confSource}</span>
        </p>
      ) : null}

      <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
          <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Decision type</dt>
          <dd className="mt-1 text-sm font-medium capitalize text-foreground">
            {readString(envelope.decision_type, "answer").replace(/_/g, " ")}
          </dd>
        </div>
        <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
          <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Freshness</dt>
          <dd className="mt-1 text-sm font-medium text-foreground">
            {envelope.freshness_status ? freshnessLabelText(envelope.freshness_status) : "—"}
          </dd>
        </div>
        <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
          <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">Learning confidence</dt>
          <dd className="mt-1">
            <LearningConfidenceBadge learning={envelope.learning_confidence} showSamples />
          </dd>
        </div>
      </dl>

      {domain.department || domain.subdomain ? (
        <div className="mt-3 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm">
          <span className="text-muted-foreground">Domain context: </span>
          <span className="font-medium text-foreground">
            {[domain.department, domain.subdomain].filter(Boolean).join(" → ")}
          </span>
        </div>
      ) : null}

      {alt && (alt.alternative_strategy_count ?? 0) > 0 ? (
        <div className="mt-3 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Strategy selection: </span>
          {alt.alternative_strategy_count} alternatives considered
          {alt.selected_strategy ? ` · selected ${alt.selected_strategy}` : ""}
          {alt.guidance_strength != null ? ` · guidance ${Math.round(alt.guidance_strength * 100)}%` : ""}
        </div>
      ) : null}

      {gaps.length ? (
        <div className="mt-3">
          <p className="text-xs font-medium text-foreground">Known gaps</p>
          <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
            {gaps.slice(0, 6).map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <Badge variant="outline" className="mt-4 border-amber-500/30 bg-amber-500/5 text-amber-900 dark:text-amber-200">
        Advisory only
      </Badge>
    </article>
  )
}
