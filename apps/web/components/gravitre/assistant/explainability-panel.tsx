"use client"

import { useState } from "react"
import Link from "next/link"
import { ChevronDown, Info } from "lucide-react"
import { cn } from "@/lib/utils"
import { DecisionTransparencyCard } from "@/components/intelligence/decision-transparency-card"
import { OptimizationVisibilityPanel } from "@/components/intelligence/optimization-visibility-panel"
import { RetrievalSummaryPanel } from "@/components/intelligence/retrieval-summary-panel"
import { SourceIntelligencePanel } from "@/components/intelligence/source-intelligence-panel"
import { ToolChip, type ToolInvocation } from "@/components/gravitre/assistant/tool-chip"
import type { DecisionTransparencyEnvelope } from "@/lib/intelligence/visibility-types"
import { CONTEXT_HELP_HREF, type ContextSourcesSummary } from "@/lib/context-sources"

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

/** The sources an answer was built from, and what was left out and why. */
export function ContextSourcesList({ sources }: { sources: ContextSourcesSummary }) {
  const hidden = Math.max(0, (sources.usedCount ?? sources.used.length) - sources.used.length)
  return (
    <div className="space-y-2">
      {sources.used.length ? (
        <div>
          <p className="font-medium text-foreground">Sources</p>
          <ul className="mt-1 space-y-1">
            {sources.used.map((row) => (
              <li key={`${row.kind}:${row.name}`} className="leading-snug">
                <span className="text-foreground">{row.name}</span>
                <span className="text-muted-foreground">
                  {" · "}
                  {row.kind}
                  {row.freshness ? ` · ${row.freshness}` : ""}
                </span>
              </li>
            ))}
            {hidden > 0 ? <li className="text-muted-foreground">and {hidden} more</li> : null}
          </ul>
        </div>
      ) : null}
      {sources.skipped.length ? (
        <div>
          <p className="font-medium text-foreground">Left out</p>
          <ul className="mt-1 space-y-1">
            {sources.skipped.map((row) => (
              <li key={row.reason || row.label}>
                {row.label} ({row.count})
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

export function ExplainabilityPanel({
  explanation,
  contextExplanation,
  contextSources,
  decisionTransparency,
  toolInvocations = [],
}: {
  explanation?: ExplainabilityEnvelope | null
  contextExplanation?: string | null
  contextSources?: ContextSourcesSummary | null
  decisionTransparency?: DecisionTransparencyEnvelope | null
  toolInvocations?: ToolInvocation[]
}) {
  const [expanded, setExpanded] = useState(false)
  const summary = contextSources?.summary || explanation?.summary || contextExplanation
  const extraContext =
    contextExplanation && contextExplanation !== summary && explanation?.summary !== contextExplanation
      ? contextExplanation
      : null
  const envelope = asTransparencyEnvelope(explanation, decisionTransparency)
  const tools = toolInvocations.filter((invocation) => invocation.state === "result")
  const hasSources = Boolean(contextSources && (contextSources.used.length || contextSources.skipped.length))
  if (!summary && !envelope && tools.length === 0 && !hasSources) return null

  return (
    <div id="why-this-answer" className="mt-3 border-t border-border/50 pt-2">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 text-left text-muted-foreground transition-colors hover:text-foreground"
      >
        <Info className="h-3.5 w-3.5 shrink-0" />
        <span className="text-[11px] font-medium">Why this answer?</span>
        <ChevronDown
          className={cn("ml-auto h-3.5 w-3.5 transition-transform", expanded && "rotate-180")}
        />
      </button>
      {expanded ? (
        <div className="mt-3 space-y-3 text-xs text-muted-foreground">
          {summary ? <p className="whitespace-pre-wrap text-foreground/90">{summary}</p> : null}
          {extraContext ? <p className="whitespace-pre-wrap">{extraContext}</p> : null}
          {contextSources && hasSources ? <ContextSourcesList sources={contextSources} /> : null}
          {tools.length > 0 ? (
            <div>
              <p className="font-medium text-foreground">Tools checked</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {tools.map((invocation) => (
                  <ToolChip key={invocation.toolCallId} invocation={invocation} />
                ))}
              </div>
            </div>
          ) : null}
          {explanation?.confidence_note ? <p>{explanation.confidence_note}</p> : null}
          {explanation?.evidence?.length ? (
            <ul className="space-y-1">
              {explanation.evidence.slice(0, 6).map((row) => (
                <li key={`${row.label}-${row.kind}`}>{row.label}</li>
              ))}
            </ul>
          ) : null}
          {explanation?.missing_context?.length ? (
            <div>
              <p className="font-medium text-foreground">What&apos;s missing</p>
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
          <p className="text-[11px] text-muted-foreground/80">
            Advisory only — verify before acting on recommendations.{" "}
            <Link href={CONTEXT_HELP_HREF} className="underline underline-offset-2 hover:text-foreground">
              How Gravitre uses your context
            </Link>
          </p>
        </div>
      ) : null}
    </div>
  )
}
