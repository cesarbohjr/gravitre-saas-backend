"use client"

/**
 * Knowledge (route /intelligence/learning): one scrolling page, no inner tabs.
 * Learnings first, then how things relate, then what Gravitre remembers.
 * Models live on the Models tab only, so this page never repeats them.
 */
import { useMemo, useState } from "react"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { LearningInsightsList } from "@/components/intelligence/learning-insight-card"
import { RelationshipsWorkspace } from "@/components/intelligence/relationships/relationships-workspace"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import type { IntelligencePageContextResponse } from "@/lib/api"
import { intelligenceApi } from "@/lib/api"
import { OrgMemorySection } from "@/components/intelligence/org-memory-section"
import { formatLearningInsights } from "@/lib/intelligence/learning-insight-display"
import {
  collectInsightFilterOptions,
  DEFAULT_LEARNING_FILTERS,
  filterLearningInsights,
  type LearningInsightFilters,
} from "@/lib/intelligence/learning-filters"
import { type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { TYPE } from "@/lib/design-system"
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
            label: "Go to memory",
            onClick: () => {
              document.getElementById("memory")?.scrollIntoView({ behavior: "smooth", block: "start" })
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
  const [filters, setFilters] = useState<LearningInsightFilters>(DEFAULT_LEARNING_FILTERS)

  const isLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"

  const insights = useMemo(
    () => formatLearningInsights(pageContext?.snapshot.learnings as Record<string, unknown>[] | undefined),
    [pageContext?.snapshot.learnings],
  )
  const hasNoBusinessLearning = pageContext?.qualityFlags?.includes("NO_BUSINESS_LEARNING_YET") ?? false

  const { data: relationshipsSnapshot, isLoading: relationshipsSnapshotLoading } = useSWR(
    enabled ? "intelligence/learning/relationships-snapshot" : null,
    () => intelligenceApi.snapshot(),
    { revalidateOnFocus: false },
  )

  return (
    <div className="space-y-10 pt-6">
      <section aria-labelledby="knowledge-learnings-heading" className="space-y-3">
        <div>
          <h2 id="knowledge-learnings-heading" className={TYPE.sectionTitle}>Recent learnings</h2>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Insights Gravitre confirmed from real work, newest first. Filter by evidence, confidence, or source.
          </p>
        </div>
        <LearnedRecentlyPanel
          insights={insights}
          isLoading={isLoading}
          hasNoBusinessLearning={hasNoBusinessLearning}
          filters={filters}
          onFiltersChange={setFilters}
        />
      </section>

      <section id="knowledge-relationships-heading" className="scroll-mt-24">
        <RelationshipsWorkspace
          data={relationshipsSnapshot}
          isLoading={relationshipsSnapshotLoading}
          enabled={enabled}
        />
      </section>

      <section id="memory" aria-labelledby="knowledge-memory-heading" className="scroll-mt-24 space-y-3">
        <div>
          <h2 id="knowledge-memory-heading" className={TYPE.sectionTitle}>Memory</h2>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            What Gravitre remembers for your whole organization, where each memory came from, and what is waiting for review.
          </p>
        </div>
        <OrgMemorySection enabled={enabled} />
      </section>

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
