"use client"

import { useState } from "react"
import { ChevronDown, Info } from "lucide-react"
import { cn } from "@/lib/utils"
import { DecisionTransparencyCard } from "@/components/intelligence/decision-transparency-card"
import { OptimizationVisibilityPanel } from "@/components/intelligence/optimization-visibility-panel"
import { RetrievalSummaryPanel } from "@/components/intelligence/retrieval-summary-panel"
import { SourceIntelligencePanel } from "@/components/intelligence/source-intelligence-panel"
import type { DecisionTransparencyEnvelope } from "@/lib/intelligence/visibility-types"

type ExplainabilityEnvelope = DecisionTransparencyEnvelope & {
  evidence?: Array<{ label?: string; kind?: string; relevance?: number }>
  confidence_note?: string
  missing_context?: string[]
  response_type?: string
}

function asTransparencyEnvelope(
  explanation?: ExplainabilityEnvelope | null,
  decisionTransparency?: DecisionTransparencyEnvelope | null,
): DecisionTransparencyEnvelope | null {
  if (decisionTransparency) return decisionTransparency
  if (!explanation) return null
  if (
    explanation.decision_type ||
    explanation.sources_used ||
    explanation.retrieval_summary ||
    explanation.confidence_band
  ) {
    return explanation
  }
  return null
}

export function ExplainabilityPanel({
  explanation,
  contextExplanation,
  decisionTransparency,
}: {
  explanation?: ExplainabilityEnvelope | null
  contextExplanation?: string | null
  decisionTransparency?: DecisionTransparencyEnvelope | null
}) {
  const [expanded, setExpanded] = useState(false)
  const summary = explanation?.summary || contextExplanation
  const envelope = asTransparencyEnvelope(explanation, decisionTransparency)
  if (!summary && !envelope) return null

  return (
    <div className="mt-2 rounded-lg border border-border/70 bg-muted/30 px-3 py-2">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center gap-2 text-left"
      >
        <Info className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[11px] font-medium text-foreground">Why this answer?</span>
        <ChevronDown
          className={cn("ml-auto h-3.5 w-3.5 text-muted-foreground transition-transform", expanded && "rotate-180")}
        />
      </button>
      {expanded ? (
        <div className="mt-3 space-y-3 text-xs text-muted-foreground">
          {summary ? <p className="whitespace-pre-wrap text-foreground/90">{summary}</p> : null}
          {explanation?.confidence_note ? <p>{explanation.confidence_note}</p> : null}
          {explanation?.evidence?.length ? (
            <ul className="space-y-1">
              {explanation.evidence.slice(0, 6).map((row) => (
                <li key={`${row.label}-${row.kind}`}>
                  {row.label}
                  {row.relevance != null ? ` (${Math.round(Number(row.relevance) * 100)}%)` : ""}
                </li>
              ))}
            </ul>
          ) : null}
          {explanation?.missing_context?.length ? (
            <div>
              <p className="font-medium text-foreground">Missing context</p>
              <ul className="mt-1 list-disc pl-4">
                {explanation.missing_context.slice(0, 6).map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {envelope ? (
            <div className="space-y-3 border-t border-border/60 pt-3">
              <DecisionTransparencyCard envelope={envelope} className="border-0 bg-transparent p-0 shadow-none" />
              <SourceIntelligencePanel envelope={envelope} />
              <RetrievalSummaryPanel summary={envelope.retrieval_summary} />
              <OptimizationVisibilityPanel
                signals={envelope.optimization_signals}
                pendingCount={
                  (envelope.trust_health as { optimization_state?: { pending_recommendations?: number } } | undefined)
                    ?.optimization_state?.pending_recommendations
                }
              />
            </div>
          ) : null}
          <p className="rounded-md border border-dashed border-amber-500/30 bg-amber-500/5 px-2 py-1 text-[11px] text-amber-900 dark:text-amber-200">
            Advisory only — verify before acting on recommendations.
          </p>
        </div>
      ) : null}
    </div>
  )
}
