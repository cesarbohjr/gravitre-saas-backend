"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  GravitreTable,
  GravitreTableShell,
  GravitreTd,
  GravitreTh,
} from "@/components/gravitre/nodus-product/table"
import { entityTypeLabel, relationshipTypeLabel } from "@/lib/learning-ui-copy"
import { confidenceLabel, confidenceTone, readNumber, relationshipEdgeId } from "@/lib/relationships-graph/utils"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { Archive, ArrowCounterClockwise, ArrowRight } from "@phosphor-icons/react"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

export function RelationshipTableView({ workspace }: { workspace: RelationshipsWorkspaceState }) {
  const {
    filtered,
    pageRows,
    pageCount,
    safePage,
    setPage,
    labelFor,
    setArchived,
    busyId,
    setSelection,
    loading,
    relationships,
    showArchived,
  } = workspace

  if (loading) {
    return <p className="p-4 text-sm text-[color:var(--g-text-muted)]">Loading relationships…</p>
  }

  if (relationships.length === 0 && !showArchived) {
    return (
      <p className="p-6 text-sm leading-relaxed text-[color:var(--g-text-muted)]">
        No learned relationships yet. They appear as Learning runs over indexed sources and glossary terms.
      </p>
    )
  }

  if (filtered.length === 0) {
    return <p className="p-6 text-sm text-[color:var(--g-text-muted)]">No relationships match these filters.</p>
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <AdaptiveDataView className="border-0">
        <GravitreTableShell>
          <GravitreTable>
            <thead>
              <tr className="border-b border-divide">
                <GravitreTh>From</GravitreTh>
                <GravitreTh>Link</GravitreTh>
                <GravitreTh>To</GravitreTh>
                <GravitreTh>Evidence</GravitreTh>
                <GravitreTh>Confidence</GravitreTh>
                <GravitreTh>
                  <span className="sr-only">Actions</span>
                </GravitreTh>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((rel) => {
                const confidence = readNumber(rel.confidence)
                const id = String(rel.id ?? "")
                const archived = Boolean(rel.archived_at)
                const edgeId = relationshipEdgeId(rel)
                return (
                  <tr
                    key={edgeId}
                    className="cursor-pointer border-b border-divide/70 last:border-0 hover:bg-[color:var(--g-surface-2)]/50"
                    onClick={() => setSelection({ kind: "edge", edgeId })}
                  >
                    <GravitreTd>
                      <span className="text-xs text-[color:var(--g-text-muted)]">
                        {entityTypeLabel(rel.source_entity_type)}
                      </span>
                      <p className="font-medium text-[color:var(--g-text-primary)]">
                        {labelFor(rel.source_entity_type, rel.source_entity_id)}
                      </p>
                    </GravitreTd>
                    <GravitreTd>
                      <span className="inline-flex items-center gap-1 text-[color:var(--g-text-muted)]">
                        <ArrowRight className="h-3.5 w-3.5 shrink-0" weight="bold" aria-hidden />
                        {relationshipTypeLabel(rel.relationship_type)}
                      </span>
                    </GravitreTd>
                    <GravitreTd>
                      <span className="text-xs text-[color:var(--g-text-muted)]">
                        {entityTypeLabel(rel.target_entity_type)}
                      </span>
                      <p className="font-medium text-[color:var(--g-text-primary)]">
                        {labelFor(rel.target_entity_type, rel.target_entity_id)}
                      </p>
                    </GravitreTd>
                    <GravitreTd className="tabular-nums">{readNumber(rel.evidence_count)}</GravitreTd>
                    <GravitreTd>
                      <Badge
                        variant="outline"
                        className={`tabular-nums ${confidenceTone(confidence)}`}
                        title={`${confidence.toFixed(2)} (estimate)`}
                      >
                        {confidenceLabel(confidence)}
                      </Badge>
                    </GravitreTd>
                    <GravitreTd className="text-right">
                      {id ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="gap-1.5"
                          disabled={busyId === id}
                          onClick={(e) => {
                            e.stopPropagation()
                            void setArchived(id, !archived)
                          }}
                        >
                          {archived ? (
                            <>
                              <ArrowCounterClockwise className="h-4 w-4" weight="bold" aria-hidden />
                              Restore
                            </>
                          ) : (
                            <>
                              <Archive className="h-4 w-4" weight="bold" aria-hidden />
                              Archive
                            </>
                          )}
                        </Button>
                      ) : null}
                    </GravitreTd>
                  </tr>
                )
              })}
            </tbody>
          </GravitreTable>
        </GravitreTableShell>
      </AdaptiveDataView>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-[color:var(--g-text-muted)]">
          Page {safePage + 1} of {pageCount}
        </p>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={safePage <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
