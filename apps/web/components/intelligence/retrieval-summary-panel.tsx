"use client"

import { MagnifyingGlass } from "@phosphor-icons/react"
import { readString } from "@/lib/intelligence/helpers"
import { formatRetrievalEffectiveness } from "@/lib/intelligence/visibility-helpers"

export function RetrievalSummaryPanel({
  summary,
  className,
}: {
  summary?: Record<string, unknown> | null
  className?: string
}) {
  if (!summary || Object.keys(summary).length === 0) {
    return (
      <div className={className}>
        <p className="text-xs text-muted-foreground">Retrieval summary unavailable — insufficient_data.</p>
      </div>
    )
  }

  const assignmentIds = (summary.assignment_ids_used as string[] | undefined) ?? []
  const memorySegments = (summary.memory_segments_used as string[] | undefined) ?? []

  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-2">
        <MagnifyingGlass className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
        <h4 className="text-sm font-medium text-foreground">Retrieval summary</h4>
      </div>
      <dl className="grid gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Domain</dt>
          <dd className="font-medium text-foreground">{readString(summary.domain, "—")}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Sources searched</dt>
          <dd className="font-medium text-foreground">
            {summary.sources_searched != null ? String(summary.sources_searched) : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Sources used</dt>
          <dd className="font-medium text-foreground">
            {summary.sources_used != null ? String(summary.sources_used) : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Retrieval effectiveness</dt>
          <dd className="font-medium text-foreground">
            {formatRetrievalEffectiveness(summary.retrieval_score as number | null | undefined)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Freshness</dt>
          <dd className="font-medium text-foreground">{readString(summary.freshness as string, "—")}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Knowledge graph</dt>
          <dd className="font-medium text-foreground">{summary.knowledge_graph_used ? "Used" : "Not used"}</dd>
        </div>
      </dl>
      {assignmentIds.length ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Assignments: {assignmentIds.slice(0, 4).join(", ")}
          {assignmentIds.length > 4 ? ` +${assignmentIds.length - 4} more` : ""}
        </p>
      ) : null}
      {memorySegments.length ? (
        <p className="mt-1 text-[11px] text-muted-foreground">
          Memory segments: {memorySegments.slice(0, 3).join(", ")}
        </p>
      ) : null}
    </div>
  )
}
