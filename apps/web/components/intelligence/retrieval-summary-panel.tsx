"use client"

import { MagnifyingGlass } from "@phosphor-icons/react"
import { readString } from "@/lib/intelligence/helpers"
import { formatRetrievalEffectiveness } from "@/lib/intelligence/visibility-helpers"

function plainWords(value: string): string {
  return value.replace(/[_-]+/g, " ").trim()
}

function listCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0
}

/**
 * What was searched for an answer, in plain words. Internal ids (knowledge
 * assignment and memory segment ids) are never shown, only how many were used.
 */
export function RetrievalSummaryPanel({
  summary,
  className,
}: {
  summary?: Record<string, unknown> | null
  className?: string
}) {
  // Nothing recorded for this answer: show nothing rather than a technical
  // "unavailable" line. The Sources list above already says what was used.
  if (!summary || Object.keys(summary).length === 0) return null

  const assignmentCount = listCount(summary.assignment_ids_used)
  const memoryCount = listCount(summary.memory_segments_used)
  const domain = readString(summary.domain)

  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-2">
        <MagnifyingGlass className="h-4 w-4 text-primary" weight="duotone" aria-hidden />
        <h4 className="text-sm font-medium text-foreground">What was searched</h4>
      </div>
      <dl className="grid gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Area</dt>
          <dd className="font-medium capitalize text-foreground">{domain ? plainWords(domain) : "—"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Sources checked</dt>
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
          <dt className="text-muted-foreground">How well the search matched</dt>
          <dd className="font-medium text-foreground">
            {formatRetrievalEffectiveness(summary.retrieval_score as number | null | undefined)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Source freshness</dt>
          <dd className="font-medium text-foreground">{readString(summary.freshness as string, "—")}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Links between your records</dt>
          <dd className="font-medium text-foreground">{summary.knowledge_graph_used ? "Used" : "Not used"}</dd>
        </div>
      </dl>
      {assignmentCount > 0 ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Used {assignmentCount} assigned knowledge {assignmentCount === 1 ? "source" : "sources"}.
        </p>
      ) : null}
      {memoryCount > 0 ? (
        <p className="mt-1 text-[11px] text-muted-foreground">
          Used {memoryCount} saved {memoryCount === 1 ? "memory" : "memories"}.
        </p>
      ) : null}
    </div>
  )
}
