"use client"

/**
 * I5 — Learning hub product surface: segmented views + quality filters.
 */
import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { SegmentedControl } from "@/components/gravitre/filter-chip"
import { LearningInsightsList } from "@/components/intelligence/learning-insight-card"
import { RelationshipsWorkspace } from "@/components/intelligence/relationships/relationships-workspace"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import type { IntelligencePageContextResponse } from "@/lib/api"
import { intelligenceApi, memoryPromotionApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { readNumber, readString } from "@/lib/intelligence/helpers"
import { formatLearningInsights } from "@/lib/intelligence/learning-insight-display"
import {
  collectInsightFilterOptions,
  DEFAULT_LEARNING_FILTERS,
  filterLearningInsights,
  type LearningInsightFilters,
  type LearningSegment,
} from "@/lib/intelligence/learning-filters"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { statusShortLabel } from "@/lib/built-in-model-catalog"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ArrowRight, Brain, Cpu } from "@phosphor-icons/react"

const SEGMENTS: { id: LearningSegment; label: string }[] = [
  { id: "recent", label: "Learned recently" },
  { id: "relationships", label: "Relationships" },
  { id: "memory", label: "Memory" },
  { id: "models", label: "Models" },
]

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
        "flex flex-wrap items-end gap-3 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)]/40 px-3 py-2.5",
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
}: {
  insights: ReturnType<typeof formatLearningInsights>
  isLoading: boolean
  hasNoBusinessLearning: boolean
  filters: LearningInsightFilters
  onFiltersChange: (next: LearningInsightFilters) => void
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
            label: "Open memory",
            onClick: () => {
              window.location.href = APP_ROUTES.intelligenceMemory
            },
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

function MemoryPanel({
  pageContext,
  metricsReady,
  isLoading,
}: {
  pageContext?: IntelligencePageContextResponse | null
  metricsReady: boolean
  isLoading: boolean
}) {
  const { data: autoData, isLoading: autoLoading } = useSWR(
    "intelligence/learning/memory-auto",
    () => memoryPromotionApi.recentAutoPromotions({ limit: 5 }),
    { revalidateOnFocus: false },
  )

  const knowledgeMetrics =
    pageContext?.metrics.knowledge ?? pageContext?.snapshot.metrics.knowledge ?? {}
  const entityTypes = pageContext?.snapshot.knowledgeEntityTypes ?? []
  const knownEntities = metricsReady ? readNumber(knowledgeMetrics.knownEntities, null) : null
  const knownRelationships = metricsReady ? readNumber(knowledgeMetrics.knownRelationships, null) : null
  const autoItems = autoData?.items ?? []

  return (
    <div className="space-y-4">
      <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-3">
        <GravitreMetric
          label="Known entities"
          value={knownEntities ?? "—"}
          hint={isLoading ? "Loading intelligence…" : "Knowledge graph scope"}
        />
        <GravitreMetric
          label="Known relationships"
          value={knownRelationships ?? "—"}
          hint={isLoading ? "Loading intelligence…" : "Entity connections"}
        />
        <GravitreMetric
          label="Recent auto-promotions"
          value={autoLoading ? "—" : autoItems.length}
          hint="Promoted org memories (sample)"
          className="col-span-2 lg:col-span-1"
        />
      </section>

      {entityTypes.length > 0 ? (
        <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-4">
          <p className={TYPE.eyebrow}>Entity types in graph</p>
          <p className="mt-2 text-sm text-muted-foreground">{entityTypes.join(" · ")}</p>
        </div>
      ) : null}

      {autoItems.length > 0 ? (
        <ul className="space-y-2">
          {autoItems.map((item, index) => (
            <li
              key={String(item.memory_id ?? index)}
              className="rounded-[var(--np-radius-md)] border border-divide px-3 py-2 text-sm"
            >
              <p className="font-medium text-foreground">
                {readString(item.promotionPath, readString(item.action, "Auto-promoted org memory"))}
              </p>
              {item.decided_at ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {new Date(String(item.decided_at)).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : !autoLoading ? (
        <EmptyState
          iconSlot={<Brain className="h-8 w-8 text-primary" weight="duotone" aria-hidden />}
          title="No recent auto-promotions"
          description="Org memory grows as recurring patterns meet promotion thresholds."
        />
      ) : null}

      <Link
        href={APP_ROUTES.intelligenceMemory}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand)] hover:underline"
      >
        Open full org memory
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </div>
  )
}

function ModelsPanel({
  pageContext,
  metricsReady,
  isLoading,
}: {
  pageContext?: IntelligencePageContextResponse | null
  metricsReady: boolean
  isLoading: boolean
}) {
  const learningMetrics =
    pageContext?.metrics.learning ?? pageContext?.snapshot.metrics.learning ?? {}
  const modelsImproved = metricsReady ? readNumber(learningMetrics.modelsImproved, null) : null
  const modelsTracked = metricsReady ? readNumber(learningMetrics.modelsTracked, null) : null
  const models = (pageContext?.snapshot.models ?? []) as Array<Record<string, unknown>>

  return (
    <div className="space-y-4">
      <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)]">
        <GravitreMetric
          label="Models tracked"
          value={modelsTracked ?? "—"}
          hint={isLoading ? "Loading intelligence…" : "Registry scope — readiness, not learning claims"}
        />
        <GravitreMetric
          label="Improved from evidence"
          value={modelsImproved ?? "—"}
          hint={isLoading ? "Loading intelligence…" : "Verified improvement outcomes only"}
        />
      </section>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading model learning signals…</p>
      ) : models.length === 0 ? (
        <EmptyState
          iconSlot={<Cpu className="h-8 w-8 text-primary" weight="duotone" aria-hidden />}
          title="No models in learning scope yet"
          description="Built-in and trained models appear here when the org catalog is active."
          action={{
            label: "Open models",
            onClick: () => {
              window.location.href = APP_ROUTES.builtInModels
            },
            variant: "outline",
          }}
        />
      ) : (
        <ul className="divide-y divide-divide border border-divide">
          {models.map((model) => {
            const id = readString(model.id, readString(model.technicalLabel, "model"))
            const label = readString(model.businessLabel, id)
            const status = readString(model.status, "unknown")
            return (
              <li key={id} className="flex items-baseline justify-between gap-3 px-3 py-2">
                <p className="text-sm font-medium text-foreground">{label}</p>
                <p className="text-xs text-muted-foreground">{statusShortLabel(status)}</p>
              </li>
            )
          })}
        </ul>
      )}

      <Link
        href={APP_ROUTES.builtInModels}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand)] hover:underline"
      >
        Open built-in models
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </div>
  )
}

export function LearningStage({
  pageContext,
  loadState,
  enabled,
  suggestedQuestions,
}: {
  pageContext?: IntelligencePageContextResponse | null
  loadState: SnapshotLoadState
  enabled: boolean
  suggestedQuestions?: string[]
}) {
  const [segment, setSegment] = useState<LearningSegment>("recent")
  const [filters, setFilters] = useState<LearningInsightFilters>(DEFAULT_LEARNING_FILTERS)

  const metricsReady = isSnapshotMetricsReady(loadState)
  const isLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"

  const insights = useMemo(
    () => formatLearningInsights(pageContext?.snapshot.learnings as Record<string, unknown>[] | undefined),
    [pageContext?.snapshot.learnings],
  )
  const hasNoBusinessLearning = pageContext?.qualityFlags?.includes("NO_BUSINESS_LEARNING_YET") ?? false

  const { data: relationshipsSnapshot, isLoading: relationshipsSnapshotLoading } = useSWR(
    enabled && segment === "relationships" ? "intelligence/learning/relationships-snapshot" : null,
    () => intelligenceApi.snapshot(),
    { revalidateOnFocus: false },
  )

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div>
          <p className={TYPE.eyebrow}>Learning views</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            What Gravitre has learned from your business — evidence, relationships, memory, and models.
          </p>
        </div>
        <SegmentedControl
          ariaLabel="Learning view"
          options={SEGMENTS}
          value={segment}
          onChange={setSegment}
          className="w-full max-w-full flex-wrap sm:w-auto"
        />
      </div>

      {segment === "recent" ? (
        <LearnedRecentlyPanel
          insights={insights}
          isLoading={isLoading}
          hasNoBusinessLearning={hasNoBusinessLearning}
          filters={filters}
          onFiltersChange={setFilters}
        />
      ) : null}

      {segment === "relationships" ? (
        <RelationshipsWorkspace
          data={relationshipsSnapshot}
          isLoading={relationshipsSnapshotLoading}
          enabled={enabled}
        />
      ) : null}

      {segment === "memory" ? (
        <MemoryPanel pageContext={pageContext} metricsReady={metricsReady} isLoading={isLoading} />
      ) : null}

      {segment === "models" ? (
        <ModelsPanel pageContext={pageContext} metricsReady={metricsReady} isLoading={isLoading} />
      ) : null}

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
