/** Phase 4 — confidence and sources display for adaptive research cascade. */
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
  const sourceCount = cascade.source_count ?? cascade.top_sources?.length ?? 0
  const summaryBits = [
    formatConfidenceBand(cascade.confidence_band),
    sourceCount ? `${sourceCount} source${sourceCount === 1 ? "" : "s"}` : null,
  ].filter(Boolean)

  return (
    <details className={cn("text-sm", className)}>
      <summary className="cursor-pointer text-xs text-muted-foreground">
        Research{summaryBits.length ? ` · ${summaryBits.join(" · ")}` : ""}
      </summary>
      <div className="mt-2 space-y-3">
      {hasScores ? (
        <>
          {cascade.retrieval_score != null ? (
            <p className="text-xs text-muted-foreground">
              Score {formatRetrievalScore(cascade.retrieval_score)}
            </p>
          ) : null}

          {Object.keys(breakdown).length > 0 ? (
            <p className="text-xs text-muted-foreground">
              {Object.entries(breakdown)
                .map(([kind, count]) => `${kindLabel(kind)} · ${count}`)
                .join(" · ")}
            </p>
          ) : null}

          {(cascade.top_sources?.length ?? 0) > 0 ? (
            <ul className="space-y-1 text-xs text-muted-foreground">
              {cascade.top_sources!.slice(0, 4).map((source, index) => {
                const url = source.url?.trim()
                const isExternal = url?.startsWith("http://") || url?.startsWith("https://")
                return (
                  <li key={`${source.source_name}-${index}`} className="truncate">
                    {isExternal ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-foreground underline-offset-2 hover:underline"
                      >
                        {source.source_name ?? "Source"}
                      </a>
                    ) : (
                      <span className="text-foreground">{source.source_name ?? "Source"}</span>
                    )}
                    {source.score != null ? ` · ${formatRetrievalScore(source.score)}` : ""}
                    {source.source_type ? ` · ${kindLabel(String(source.source_type))}` : ""}
                  </li>
                )
              })}
            </ul>
          ) : null}
        </>
      ) : null}

      {hasActions ? (
        <div className={cn(hasScores && "border-t border-border/50 pt-3")}>
          <p className="text-xs font-medium text-muted-foreground">Suggested follow-up actions</p>
          <ul className="mt-2 space-y-2">
            {cascade.research_actions!.map((action) => (
              <li
                key={action.invoke_action ?? action.label}
                className="flex items-start gap-2 py-1 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-foreground">{action.label ?? action.invoke_action}</p>
                  {action.rationale ? (
                    <p className="mt-0.5 text-muted-foreground">{action.rationale}</p>
                  ) : null}
                </div>
                {action.requires_approval ? (
                  <span className="inline-flex shrink-0 items-center gap-1 text-[10px] font-medium text-amber-900 dark:text-amber-100">
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
    </details>
  )
}
