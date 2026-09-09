"use client"

import { Button } from "@/components/ui/button"
import { GravitreSurface } from "@/components/gravitre/nodus-product/metric"
import { RELATIONSHIPS_GUIDE } from "@/lib/learning-ui-copy"
import { Info, Plus } from "@phosphor-icons/react"
import { AddKnowledgeNodeSheet } from "./add-knowledge-node-sheet"
import { RelationshipGraphCanvas } from "./relationship-graph-canvas"
import { RelationshipInspector } from "./relationship-inspector"
import { RelationshipMetrics } from "./relationship-metrics"
import { RelationshipTableView } from "./relationship-table-view"
import { RelationshipToolbar } from "./relationship-toolbar"
import { useRelationshipsWorkspace } from "./use-relationships-workspace"
import type { IntelligenceSnapshot } from "@/lib/api"

export function RelationshipsWorkspace({
  data,
  isLoading,
  enabled,
}: {
  data: IntelligenceSnapshot | undefined
  isLoading: boolean
  enabled: boolean
}) {
  const workspace = useRelationshipsWorkspace({ data, isLoading, enabled })
  const {
    loading,
    nodes,
    nodesLoading,
    relationships,
    filtered,
    viewMode,
    selection,
    setSelection,
    setAddNodeOpen,
  } = workspace

  const showSeedBanner =
    nodes.length === 0 && relationships.filter((r) => !r.archived_at).length > 0 && !nodesLoading

  return (
    <div className="space-y-4">
      <section
        aria-labelledby="relationships-guide-heading"
        className="rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/40 px-4 py-3 sm:px-5"
      >
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
            <Info className="h-4 w-4" weight="duotone" aria-hidden />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id="relationships-guide-heading" className="text-sm font-semibold text-[color:var(--g-text-primary)]">
              {RELATIONSHIPS_GUIDE.title}
            </h2>
            <p className="text-sm leading-relaxed text-[color:var(--g-text-muted)]">{RELATIONSHIPS_GUIDE.lead}</p>
          </div>
        </div>
      </section>

      <RelationshipMetrics workspace={workspace} />

      {showSeedBanner ? (
        <div className="flex flex-col gap-3 rounded-[var(--np-radius-lg)] border border-amber-300/60 bg-amber-50/50 px-4 py-3 dark:bg-amber-950/20 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
            Gravitre has learned relationships but no organization knowledge is seeded yet. Add a company, person, or
            product so agents can resolve those names when answering.
          </p>
          <Button type="button" size="sm" className="shrink-0 gap-1.5" onClick={() => setAddNodeOpen(true)}>
            <Plus className="h-4 w-4" weight="bold" aria-hidden />
            Seed first entity
          </Button>
        </div>
      ) : null}

      <GravitreSurface padded={false} className="overflow-hidden">
        <div className="border-b border-divide p-4">
          <RelationshipToolbar workspace={workspace} />
        </div>

        {loading ? (
          <p className="p-6 text-sm text-[color:var(--g-text-muted)]">Loading relationships…</p>
        ) : (
          <div className="flex min-h-[480px] flex-col lg:flex-row">
            <div className="min-h-[420px] min-w-0 flex-1">
              {viewMode === "graph" ? (
                <RelationshipGraphCanvas workspace={workspace} />
              ) : (
                <RelationshipTableView workspace={workspace} />
              )}
            </div>
            <aside className="hidden w-full shrink-0 border-t border-divide lg:block lg:w-80 lg:border-l lg:border-t-0">
              <RelationshipInspector workspace={workspace} />
            </aside>
          </div>
        )}
      </GravitreSurface>

      {selection ? (
        <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] lg:hidden">
          <RelationshipInspector workspace={workspace} onClose={() => setSelection(null)} />
        </div>
      ) : null}

      {!loading && filtered.length === 0 && relationships.length === 0 && nodes.length === 0 ? (
        <p className="text-center text-sm leading-relaxed text-[color:var(--g-text-muted)]">
          {RELATIONSHIPS_GUIDE.linksEmpty}
        </p>
      ) : null}

      <AddKnowledgeNodeSheet workspace={workspace} />
    </div>
  )
}
