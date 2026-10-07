"use client"

/**
 * Knowledge (route /intelligence/learning) has three in-page views, chosen by
 * the Graph / Entities / Memory control and kept in the URL (?view=, #memory):
 * - Graph: the knowledge graph and recent learnings.
 * - Entities: the same workspace as a table of how entities link.
 * - Memory: how a memory is earned, the review queue and the inspector.
 * Models live on the Models tab only, so this page never repeats them.
 */
import { useMemo, useState } from "react"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { LearningInsightsList } from "@/components/intelligence/learning-insight-card"
import { RelationshipsWorkspace } from "@/components/intelligence/relationships/relationships-workspace"
import type { IntelligencePageContextResponse } from "@/lib/api"
import { intelligenceApi } from "@/lib/api"
import { OrgMemorySection } from "@/components/intelligence/org-memory-section"
import { useOrgMemory } from "@/components/intelligence/knowledge/use-org-memory"
import type { KnowledgeView } from "@/components/intelligence/knowledge/knowledge-view"
import { KnowledgeCard } from "@/components/intelligence/knowledge/knowledge-card"
import { countKnownEntities } from "@/components/intelligence/knowledge/knowledge-entities"
import type { RelationshipRow } from "@/lib/relationships-graph/types"
import { readNumber } from "@/lib/intelligence/helpers"
import { formatLearningInsights } from "@/lib/intelligence/learning-insight-display"
import {
  collectInsightFilterOptions,
  DEFAULT_LEARNING_FILTERS,
  filterLearningInsights,
  type LearningInsightFilters,
} from "@/lib/intelligence/learning-filters"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { cn } from "@/lib/utils"

function LearningFilterRow({
  filters,
  onChange,
  confidenceOptions,
  sourceOptions,
  disabled,
}: {
  filters: LearningInsightFilters
  onChange: (next: LearningInsightFilters) => void
  confidenceOptions: string[]
  sourceOptions: string[]
  disabled?: boolean
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end gap-3 rounded-[12px] bg-[color:var(--g-surface-2)] px-4 py-3",
        disabled && "pointer-events-none opacity-60",
      )}
      aria-hidden={disabled}
    >
      <FilterSelect
        label="Evidence quality"
        value={filters.evidenceQuality}
        options={[
          { value: "all", label: "All" },
          { value: "verified", label: "Has evidence" },
          { value: "needs_evidence", label: "Needs evidence" },
        ]}
        onChange={(evidenceQuality) =>
          onChange({ ...filters, evidenceQuality: evidenceQuality as LearningInsightFilters["evidenceQuality"] })
        }
      />
      <FilterSelect
        label="Confidence"
        value={filters.confidence}
        options={[
          { value: "all", label: "All" },
          ...confidenceOptions.map((c) => ({ value: c, label: c.replace(/_/g, " ") })),
        ]}
        onChange={(confidence) => onChange({ ...filters, confidence: confidence ?? "all" })}
      />
      <FilterSelect
        label="Source"
        value={filters.source}
        options={[
          { value: "all", label: "All" },
          ...sourceOptions.map((s) => ({ value: s, label: s.replace(/_/g, " ") })),
        ]}
        onChange={(source) => onChange({ ...filters, source: source ?? "all" })}
      />
      <FilterSelect
        label="Time range"
        value={filters.timeRange}
        options={[
          { value: "all", label: "All time" },
          { value: "7d", label: "Last 7 days" },
          { value: "30d", label: "Last 30 days" },
          { value: "90d", label: "Last 90 days" },
        ]}
        onChange={(timeRange) =>
          onChange({ ...filters, timeRange: (timeRange ?? "all") as LearningInsightFilters["timeRange"] })
        }
      />
    </div>
  )
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string | null) => void
}) {
  return (
    <label className="flex min-w-[7.5rem] flex-1 flex-col gap-0.5 sm:max-w-[10rem]">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value || null)}
        className="h-8 rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 text-xs text-foreground"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function LearnedRecentlyPanel({
  insights,
  isLoading,
  hasNoBusinessLearning,
  filters,
  onFiltersChange,
  onGoToMemory,
}: {
  insights: ReturnType<typeof formatLearningInsights>
  isLoading: boolean
  hasNoBusinessLearning: boolean
  filters: LearningInsightFilters
  onFiltersChange: (next: LearningInsightFilters) => void
  onGoToMemory: () => void
}) {
  const { confidenceOptions, sourceOptions } = useMemo(
    () => collectInsightFilterOptions(insights),
    [insights],
  )
  const filtered = useMemo(() => filterLearningInsights(insights, filters), [insights, filters])

  return (
    <div className="space-y-4">
      <LearningFilterRow
        filters={filters}
        onChange={onFiltersChange}
        confidenceOptions={confidenceOptions}
        sourceOptions={sourceOptions}
        disabled={isLoading}
      />

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading business learning insights…</p>
      ) : insights.length === 0 || hasNoBusinessLearning ? (
        <EmptyState
          variant="ai"
          title="No validated business learning yet"
          description="Insights appear here when Gravitre records durable business understanding from real work — not deployment health or training readiness."
          action={{
            label: "Go to memory",
            onClick: onGoToMemory,
            variant: "outline",
          }}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No insights match these filters"
          description="Try widening evidence quality, confidence, source, or time range."
        />
      ) : (
        <LearningInsightsList insights={filtered} />
      )}
    </div>
  )
}

const VIEW_LABELS: Record<KnowledgeView, string> = {
  graph: "Graph",
  entities: "Entities",
  memory: "Memory",
}

function KnowledgeViewSwitch({
  view,
  onViewChange,
  entityCount,
}: {
  view: KnowledgeView
  onViewChange: (view: KnowledgeView) => void
  entityCount: number | null
}) {
  const views: KnowledgeView[] = ["graph", "entities", "memory"]
  return (
    <div
      role="tablist"
      aria-label="Knowledge views"
      className="inline-flex rounded-[10px] bg-[color:var(--g-surface-2)] p-[3px]"
    >
      {views.map((id) => {
        const active = view === id
        return (
          <button
            key={id}
            type="button"
            role="tab"
            id={`knowledge-view-${id}`}
            aria-selected={active}
            aria-controls="knowledge-view-panel"
            onClick={() => onViewChange(id)}
            className={cn(
              "min-h-9 rounded-[8px] px-3.5 text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]",
              active
                ? "bg-[color:var(--g-surface-1)] font-medium text-[color:var(--g-text-primary)] shadow-[0_1px_2px_rgba(0,0,0,0.08)]"
                : "text-[color:var(--g-text-secondary)] hover:text-[color:var(--g-text-primary)]",
            )}
          >
            {VIEW_LABELS[id]}
            {id === "entities" && entityCount != null ? ` · ${entityCount}` : ""}
          </button>
        )
      })}
    </div>
  )
}

export function LearningStage({
  pageContext,
  loadState,
  enabled,
  view,
  onViewChange,
}: {
  pageContext?: IntelligencePageContextResponse | null
  loadState: SnapshotLoadState
  enabled: boolean
  view: KnowledgeView
  onViewChange: (view: KnowledgeView) => void
}) {
  const [filters, setFilters] = useState<LearningInsightFilters>(DEFAULT_LEARNING_FILTERS)
  /** null = follow the default (on only while there are no real candidates). */
  const [exampleChoice, setExampleChoice] = useState<boolean | null>(null)

  const isLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"
  const metricsReady = isSnapshotMetricsReady(loadState)

  const insights = useMemo(
    () => formatLearningInsights(pageContext?.snapshot.learnings as Record<string, unknown>[] | undefined),
    [pageContext?.snapshot.learnings],
  )
  const hasNoBusinessLearning = pageContext?.qualityFlags?.includes("NO_BUSINESS_LEARNING_YET") ?? false
  const learningMetrics = pageContext?.metrics.learning ?? pageContext?.snapshot.metrics.learning ?? {}
  const recentCount = readNumber(learningMetrics.recentLearnings, insights.length)

  const { data: relationshipsSnapshot, isLoading: relationshipsSnapshotLoading } = useSWR(
    enabled && view !== "memory" ? "intelligence/learning/relationships-snapshot" : null,
    () => intelligenceApi.snapshot(),
    { revalidateOnFocus: false },
  )
  // Same key and fetcher as the relationships workspace, so SWR shares one request.
  const { data: nodesData } = useSWR(enabled ? ["admin/intelligence/knowledge-nodes"] : null, () =>
    intelligenceApi.knowledgeNodes({ limit: 100 }),
  )
  // Same key and fetcher as the relationships workspace's active list.
  const { data: relationshipsList } = useSWR(
    enabled ? ["admin/intelligence/relationships-list", "active"] : null,
    () => intelligenceApi.relationships({ includeArchived: false, limit: 500 }),
  )
  const entityCount =
    nodesData && relationshipsList
      ? countKnownEntities(
          nodesData.nodes as RelationshipRow[],
          (relationshipsList.relationships as RelationshipRow[] | undefined) ?? [],
        )
      : null

  const memory = useOrgMemory(enabled && view === "memory")
  const previewExample = exampleChoice ?? (!memory.isLoading && !memory.error && !memory.hasRealCandidates)

  return (
    <div className="space-y-6 pt-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <KnowledgeViewSwitch view={view} onViewChange={onViewChange} entityCount={entityCount} />
        {view === "memory" ? (
          <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-[13px] text-[color:var(--g-text-secondary)]">
            <input
              type="checkbox"
              className="h-[18px] w-[18px] accent-[color:var(--g-brand-active)]"
              checked={previewExample}
              onChange={(e) => setExampleChoice(e.target.checked)}
            />
            Preview with an example memory
          </label>
        ) : null}
      </div>

      <div id="knowledge-view-panel" role="tabpanel" aria-labelledby={`knowledge-view-${view}`} className="space-y-6">
        {view === "graph" ? (
          <>
            <section id="knowledge-relationships-heading" className="scroll-mt-24">
              <RelationshipsWorkspace
                data={relationshipsSnapshot}
                isLoading={relationshipsSnapshotLoading}
                enabled={enabled}
                viewMode="graph"
                onViewModeChange={(mode) => onViewChange(mode === "table" ? "entities" : "graph")}
              />
            </section>

            <KnowledgeCard
              id="knowledge-learnings-heading"
              title="Recent learnings"
              lead="Insights Gravitre confirmed from real work, newest first. Filter by evidence, confidence, or source."
              aside={
                metricsReady && recentCount > 0 ? (
                  <span className="inline-flex items-center rounded-full bg-[color:var(--g-surface-2)] px-3 py-1.5 text-[13px] tabular-nums text-[color:var(--g-text-secondary)]">
                    {recentCount} confirmed
                  </span>
                ) : null
              }
            >
              <LearnedRecentlyPanel
                insights={insights}
                isLoading={isLoading}
                hasNoBusinessLearning={hasNoBusinessLearning}
                filters={filters}
                onFiltersChange={setFilters}
                onGoToMemory={() => onViewChange("memory")}
              />
            </KnowledgeCard>
          </>
        ) : null}

        {view === "entities" ? (
          <section id="knowledge-relationships-heading" className="scroll-mt-24">
            <RelationshipsWorkspace
              data={relationshipsSnapshot}
              isLoading={relationshipsSnapshotLoading}
              enabled={enabled}
              viewMode="table"
              onViewModeChange={(mode) => onViewChange(mode === "table" ? "entities" : "graph")}
            />
          </section>
        ) : null}

        {view === "memory" ? (
          <section id="memory" aria-label="Memory" className="scroll-mt-24">
            <OrgMemorySection memory={memory} previewExample={previewExample} />
          </section>
        ) : null}
      </div>

    </div>
  )
}
