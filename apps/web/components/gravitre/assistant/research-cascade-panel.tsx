"""Phase 4 — confidence and sources display for adaptive research cascade."""
"use client"

import { ShieldAlert } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  formatConfidenceBand,
  formatRetrievalScore,
  kindLabel,
  type ResearchCascadePayload,
} from "./research-cascade-types"

type ResearchCascadePanelProps = {
  cascade: ResearchCascadePayload | null | undefined
  className?: string
}

function bandClass(band?: string | null): string {
  switch (band) {
    case "high":
      return "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200"
    case "medium":
      return "bg-amber-500/15 text-amber-900 dark:text-amber-100"
    case "low":
      return "bg-rose-500/15 text-rose-900 dark:text-rose-100"
    default:
      return "bg-muted text-muted-foreground"
  }
}

export function ResearchCascadePanel({ cascade, className }: ResearchCascadePanelProps) {
  if (!cascade) return null

  const hasScores =
    cascade.retrieval_score != null ||
    cascade.source_count != null ||
    (cascade.top_sources?.length ?? 0) > 0 ||
    (cascade.source_breakdown && Object.keys(cascade.source_breakdown).length > 0)

  const hasActions = (cascade.research_actions?.length ?? 0) > 0

  if (!hasScores && !hasActions) return null

  const breakdown = cascade.source_breakdown ?? {}

  return (
    <div
      className={cn(
        "rounded-xl border border-border/60 bg-card/50 px-4 py-3 text-sm",
        className,
      )}
    >
      {hasScores ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">Research confidence</span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                bandClass(cascade.confidence_band),
              )}
            >
              {formatConfidenceBand(cascade.confidence_band)}
            </span>
            {cascade.retrieval_score != null ? (
              <span className="text-xs text-muted-foreground">
                Score {formatRetrievalScore(cascade.retrieval_score)}
              </span>
            ) : null}
            {cascade.source_count != null ? (
              <span className="text-xs text-muted-foreground">
                {cascade.source_count} source{cascade.source_count === 1 ? "" : "s"}
              </span>
            ) : null}
          </div>

          {Object.keys(breakdown).length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {Object.entries(breakdown).map(([kind, count]) => (
                <span
                  key={kind}
                  className="rounded-md border border-border/50 bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  {kindLabel(kind)} · {count}
                </span>
              ))}
            </div>
          ) : null}

          {(cascade.top_sources?.length ?? 0) > 0 ? (
            <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
              {cascade.top_sources!.slice(0, 4).map((source, index) => (
                <li key={`${source.source_name}-${index}`} className="truncate">
                  <span className="text-foreground">{source.source_name ?? "Source"}</span>
                  {source.score != null ? ` · ${formatRetrievalScore(source.score)}` : ""}
                  {source.source_type ? ` · ${kindLabel(String(source.source_type))}` : ""}
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}

      {hasActions ? (
        <div className={cn(hasScores && "mt-3 border-t border-border/50 pt-3")}>
          <p className="text-xs font-medium text-muted-foreground">Suggested follow-up actions</p>
          <ul className="mt-2 space-y-2">
            {cascade.research_actions!.map((action) => (
              <li
                key={action.invoke_action ?? action.label}
                className="flex items-start gap-2 rounded-lg border border-border/40 bg-muted/20 px-2.5 py-2 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-foreground">{action.label ?? action.invoke_action}</p>
                  {action.rationale ? (
                    <p className="mt-0.5 text-muted-foreground">{action.rationale}</p>
                  ) : null}
                </div>
                {action.requires_approval ? (
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-900 dark:text-amber-100">
                    <ShieldAlert className="h-3 w-3" aria-hidden />
                    Approval required
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
          {cascade.has_gated_actions ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Write actions are gated by catalog authority — confirm before execution.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
