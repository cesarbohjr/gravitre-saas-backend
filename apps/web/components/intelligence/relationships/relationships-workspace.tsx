"use client"

import { Button } from "@/components/ui/button"
import { Sheet, SheetContent } from "@/components/ui/sheet"
import { KnowledgeCard } from "@/components/intelligence/knowledge/knowledge-card"
import { RELATIONSHIPS_GUIDE, RELATIONSHIPS_ONBOARDING } from "@/lib/learning-ui-copy"
import { Plus } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"
import { AddKnowledgeNodeSheet } from "./add-knowledge-node-sheet"
import { RelationshipGraphCanvas } from "./relationship-graph-canvas"
import { RelationshipInspector } from "./relationship-inspector"
import { RelationshipTableView } from "./relationship-table-view"
import { RelationshipToolbar } from "./relationship-toolbar"
import { useRelationshipsWorkspace } from "./use-relationships-workspace"
import type { IntelligenceSnapshot } from "@/lib/api"
import type { ViewMode } from "@/lib/relationships-graph/types"

export function RelationshipsWorkspace({
  data,
  isLoading,
  enabled,
  viewMode: controlledViewMode,
  onViewModeChange,
}: {
  data: IntelligenceSnapshot | undefined
  isLoading: boolean
  enabled: boolean
  /** Controlled graph/table mode; the in-toolbar toggle hides when set. */
  viewMode?: ViewMode
  onViewModeChange?: (mode: ViewMode) => void
}) {
  const workspace = useRelationshipsWorkspace({
    data,
    isLoading,
    enabled,
    viewMode: controlledViewMode,
    onViewModeChange,
  })
  const {
    loading,
    nodes,
    nodesLoading,
    relationships,
    filtered,
    viewMode,
    selection,
    setSelection,
    openAddNode,
    inspectorOpen,
    setInspectorOpen,
  } = workspace

  const showOnboarding =
    nodes.length === 0 && relationships.filter((r) => !r.archived_at).length > 0 && !nodesLoading

  const totalCount = relationships.length
  const shownLabel =
    filtered.length === totalCount
      ? `${filtered.length} ${filtered.length === 1 ? "link" : "links"}`
      : `${filtered.length} of ${totalCount} links`

  return (
    <div className="space-y-4">
      <KnowledgeCard
        id="relationships-guide-heading"
        title={viewMode === "graph" ? RELATIONSHIPS_GUIDE.title : "How entities link"}
        titleSize="lg"
        lead={
          viewMode === "graph"
            ? RELATIONSHIPS_GUIDE.lead
            : "Every link Gravitre learned between two entities, with its evidence and confidence. Select a row to see why it exists."
        }
        padded={false}
        aside={
          loading ? null : (
            <span className="inline-flex items-center rounded-full bg-[color:var(--g-surface-2)] px-3 py-1.5 text-[13px] tabular-nums text-[color:var(--g-text-secondary)]">
              {shownLabel}
            </span>
          )
        }
      >
        {showOnboarding ? (
          <div className="mx-5 mb-4 flex flex-col gap-3 rounded-[14px] border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)] px-4 py-4 sm:mx-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-semibold text-[color:var(--g-text-primary)]">
                {RELATIONSHIPS_ONBOARDING.title}
              </p>
              <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
                {RELATIONSHIPS_ONBOARDING.lead}
              </p>
            </div>
            <Button type="button" size="sm" className="shrink-0 gap-1.5" onClick={() => openAddNode("first")}>
              <Plus className="h-4 w-4" weight="bold" aria-hidden />
              {RELATIONSHIPS_ONBOARDING.cta}
            </Button>
          </div>
        ) : null}

        <div className="border-b border-divide px-5 pb-4 sm:px-6">
          <RelationshipToolbar workspace={workspace} hideAddEntity={showOnboarding} />
        </div>

        {loading ? (
          <p className="p-6 text-sm text-[color:var(--g-text-muted)]">Loading relationships…</p>
        ) : (
          <div className={cn("flex flex-col lg:flex-row", viewMode === "graph" && "min-h-[480px]")}>
            <div className={cn("min-w-0 flex-1", viewMode === "graph" && "min-h-[420px]")}>
              {viewMode === "graph" ? (
                <RelationshipGraphCanvas workspace={workspace} />
              ) : (
                <RelationshipTableView workspace={workspace} />
              )}
            </div>
            {selection ? (
              <aside className="hidden min-h-[420px] w-full shrink-0 border-t border-divide lg:block lg:w-80 lg:border-l lg:border-t-0">
                <RelationshipInspector
                  workspace={workspace}
                  onClose={() => {
                    setSelection(null)
                    setInspectorOpen(false)
                  }}
                />
              </aside>
            ) : null}
          </div>
        )}
      </KnowledgeCard>

      {selection ? (
        <Sheet
          open={inspectorOpen}
          onOpenChange={(open) => {
            setInspectorOpen(open)
            if (!open) setSelection(null)
          }}
        >
          <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md lg:hidden">
            <RelationshipInspector
              workspace={workspace}
              onClose={() => {
                setSelection(null)
                setInspectorOpen(false)
              }}
            />
          </SheetContent>
        </Sheet>
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
