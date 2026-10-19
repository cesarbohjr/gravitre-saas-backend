"use client"

import { Badge } from "@/components/ui/badge"
import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"
import { AdvisoryOnlyNote } from "@/components/intelligence/advisory-only-note"
import { LearningConfidenceBadge } from "@/components/intelligence/learning-confidence-badge"
import { readString } from "@/lib/intelligence/helpers"
import { freshnessLabelText } from "@/lib/intelligence/visibility-helpers"
import type { DecisionTransparencyEnvelope } from "@/lib/intelligence/visibility-types"
import { KnowledgeCitationCard, type KnowledgeCitation } from "@/components/intelligence/knowledge-citation-card"

/** Plain wording for how the answer was produced. Unknown values are not shown. */
export function answerMethodLabel(runtimeStatus: string | undefined): string | null {
  switch ((runtimeStatus ?? "").trim().toLowerCase()) {
    case "heuristic":
      return "Built-in rules"
    case "trained":
    case "model_loaded":
    case "trained_model":
      return "Trained model"
    default:
      return null
  }
}

function plainWords(value: string): string {
  return value.replace(/[_-]+/g, " ").trim()
}

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
  const method = answerMethodLabel(envelope.runtime_status)
  const confSource = envelope.confidence_source ?? envelope.confidenceSource

  return (
    <article className={`rounded-2xl border border-border/70 bg-card p-4 md:p-5 ${className ?? ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-foreground">How this answer was put together</h3>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">
            What Gravitre looked at. Private reasoning isn&apos;t shown.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {method ? (
            <Badge
              variant="outline"
              className="border-info/30 bg-info/5 font-normal text-info"
              title={
                method === "Built-in rules"
                  ? "Answered with built-in rules, not a model trained on your data."
                  : "Answered with a model trained on your data."
              }
            >
              {method}
            </Badge>
          ) : null}
          <ConfidenceBadge score={envelope.confidence} isEstimate={isEstimate} />
        </div>
      </div>
      {confSource ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Confidence based on:{" "}
          <span className="font-medium text-foreground">{plainWords(String(confSource))}</span>
        </p>
      ) : null}

      <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
          <dt className="text-xs text-muted-foreground font-medium">Type of answer</dt>
          <dd className="mt-1 text-sm font-medium capitalize text-foreground">
            {plainWords(readString(envelope.decision_type, "answer"))}
          </dd>
        </div>
        <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
          <dt className="text-xs text-muted-foreground font-medium">Source freshness</dt>
          <dd className="mt-1 text-sm font-medium text-foreground">
            {envelope.freshness_status ? freshnessLabelText(envelope.freshness_status) : "—"}
          </dd>
        </div>
        <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
          <dt className="text-xs text-muted-foreground font-medium">Learned from past results</dt>
          <dd className="mt-1">
            <LearningConfidenceBadge learning={envelope.learning_confidence} showSamples />
          </dd>
        </div>
      </dl>

      {domain.department || domain.subdomain ? (
        <div className="mt-3 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm">
          <span className="text-muted-foreground">Area: </span>
          <span className="font-medium text-foreground">
            {[domain.department, domain.subdomain]
              .filter(Boolean)
              .map((value) => plainWords(String(value)))
              .join(" → ")}
          </span>
        </div>
      ) : null}

      {alt && (alt.alternative_strategy_count ?? 0) > 0 ? (
        <div className="mt-3 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Other approaches considered: </span>
          {alt.alternative_strategy_count}
        </div>
      ) : null}

      {gaps.length ? (
        <div className="mt-3">
          <p className="text-xs font-medium text-foreground">What&apos;s missing</p>
          <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
            {gaps.slice(0, 6).map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {(() => {
        const sources = (envelope as { sources?: KnowledgeCitation[]; knowledge_citations?: KnowledgeCitation[] })
          .knowledge_citations
          ?? (envelope as { sources?: KnowledgeCitation[] }).sources
          ?? []
        const fabric = sources.filter(
          (s) =>
            s &&
            (typeof s.authority_score === "number" ||
              Boolean(s.citation) ||
              Boolean(s.jurisdiction)),
        )
        return fabric.length ? (
          <KnowledgeCitationCard citations={fabric.slice(0, 6)} className="mt-4" />
        ) : null
      })()}

      <AdvisoryOnlyNote className="mt-4" />
    </article>
  )
}
