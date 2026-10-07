"use client"

/**
 * Models v2 (Build / Models): stat strip, search + filter chips, "Where models
 * are used" lineage, model cards and the "Suggested by Gravitre" card. All data
 * comes from `useModelsData` (registry, version metrics, training jobs,
 * datasets) and the built-in catalog; nothing is sample data.
 */
import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { EmptyState } from "@/components/gravitre/empty-state"
import { BusinessModelCard } from "@/components/intelligence/business-model-card"
import { ModelUsageTopology, type ModelUsageRow } from "@/components/intelligence/model-usage-topology"
import { ModelSuggestionCard } from "@/components/intelligence/models/model-suggestion-card"
import {
  attentionFor,
  isInProduction,
  matchesFilter,
  matchesSearch,
  type ModelFilter,
} from "@/components/intelligence/models/model-insights"
import type { useModelsData } from "@/components/intelligence/models/use-models-data"
import { Input } from "@/components/ui/input"
import { mlModelsApi, trainingApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import type { BuiltInModelListItem } from "@/lib/built-in-model-catalog"
import { TYPE } from "@/lib/design-system"
import { modelTypeMeta } from "@/lib/ml-registry-catalog"
import { cn } from "@/lib/utils"
import type { MlModelSummary } from "@/types/api"
import { Search } from "lucide-react"

const DISMISSED_KEY = "gravitre.models.dismissedSuggestions"

function readDismissed(): string[] {
  try {
    const raw = window.localStorage.getItem(DISMISSED_KEY)
    const parsed = raw ? (JSON.parse(raw) as unknown) : []
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : []
  } catch {
    return []
  }
}

function StatCell({ label, value, dot }: { label: string; value: string; dot?: string }) {
  return (
    <div className="flex flex-col gap-1 border-[color:var(--g-border-subtle)] px-5 py-4 [&:not(:last-child)]:border-r max-md:[&:nth-child(2)]:border-r-0 max-md:[&:nth-child(-n+2)]:border-b">
      <span className="flex items-center gap-1.5 text-[13px] text-[color:var(--g-text-secondary)]">
        {dot ? <span className={cn("h-[7px] w-[7px] rounded-full", dot)} aria-hidden /> : null}
        {label}
      </span>
      <span className="text-[26px] font-semibold tabular-nums text-[color:var(--g-text-primary)]">{value}</span>
    </div>
  )
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "min-h-9 rounded-full px-3.5 text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-foreground text-background"
          : "border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] text-[color:var(--g-text-primary)] hover:border-[color:var(--g-border-strong)]",
      )}
    >
      {children}
    </button>
  )
}

export function ModelsStage({
  data,
  builtInItems,
  builtInSuggestions,
  onRegister,
}: {
  data: ReturnType<typeof useModelsData>
  builtInItems: BuiltInModelListItem[]
  builtInSuggestions: BuiltInModelListItem[]
  onRegister?: () => void
}) {
  const router = useRouter()
  const { models, details, jobs, datasetNames, isLoading } = data
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<ModelFilter>("all")
  const [showTechnical, setShowTechnical] = useState(false)
  const [retrainingId, setRetrainingId] = useState<string | null>(null)
  const [deployingId, setDeployingId] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState<string[]>([])

  useEffect(() => {
    setDismissed(readDismissed())
  }, [])

  const counts = useMemo(() => {
    const production = models.filter(isInProduction).length
    const attention = models.filter((m) => attentionFor(m, details[m.id], jobs) != null).length
    return { all: models.length, production, registered: models.length - production, attention }
  }, [models, details, jobs])

  const visible = useMemo(
    () => models.filter((m) => matchesFilter(m, filter) && matchesSearch(m, query)),
    [models, filter, query],
  )

  const lineage: ModelUsageRow[] = useMemo(
    () =>
      visible.map((m) => ({
        id: m.id,
        name: m.name,
        live: isInProduction(m),
        learnsFrom: m.datasetId ? [datasetNames[m.datasetId] ?? "Training dataset"] : [],
        technical: [modelTypeMeta(m.modelType)?.label, m.baseModel].filter(Boolean).join(" · ") || null,
      })),
    [visible, datasetNames],
  )

  const suggestion = builtInSuggestions.find((item) => !dismissed.includes(item.id)) ?? null

  function dismissSuggestion(id: string) {
    const next = [...dismissed, id]
    setDismissed(next)
    try {
      window.localStorage.setItem(DISMISSED_KEY, JSON.stringify(next))
    } catch {
      // Per-viewer convenience only; the card simply returns next visit.
    }
  }

  async function handleRetrain(model: MlModelSummary) {
    if (!model.datasetId || !model.baseModel) {
      toast.message("Choose training data first", {
        description: "This model has no linked dataset or base model yet. Pick them in Model Studio.",
      })
      router.push(APP_ROUTES.intelligenceModelStudio)
      return
    }
    setRetrainingId(model.id)
    try {
      await trainingApi.createJob(model.datasetId, model.baseModel)
      toast.success(`Training started for ${model.name}`, {
        description: "A new version is added to this model when the run finishes.",
      })
      await data.mutateJobs()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start training")
    } finally {
      setRetrainingId(null)
    }
  }

  async function handleDeploy(model: MlModelSummary) {
    setDeployingId(model.id)
    try {
      const result = await mlModelsApi.deploy(model.id, model.currentVersion || undefined)
      if (!result.ok) throw new Error("The deployment was not accepted")
      toast.success(`${model.name} is live`, { description: `Version ${model.currentVersion} is now in production.` })
      await data.refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Deploy failed")
    } finally {
      setDeployingId(null)
    }
  }

  const loadingFirst = isLoading && models.length === 0
  const stat = (n: number) => (loadingFirst ? "—" : String(n))

  return (
    <div className="space-y-6">
      <div
        className="grid grid-cols-2 overflow-hidden rounded-[var(--g-radius-panel)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] md:grid-cols-4"
        aria-label="Model counts"
        role="group"
      >
        <StatCell label="Models" value={stat(counts.all)} />
        <StatCell label="In production" value={stat(counts.production)} dot="bg-[color:var(--g-brand)]" />
        <StatCell label="Registered only" value={stat(counts.registered)} dot="bg-[color:var(--g-text-disabled)]" />
        <StatCell
          label="Need attention"
          value={loadingFirst || (data.detailsLoading && counts.attention === 0) ? "—" : String(counts.attention)}
          dot="bg-[color:var(--g-warning)]"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2.5">
        <label htmlFor="models-search" className="sr-only">
          Search models
        </label>
        <div className="relative w-full sm:w-[300px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--g-text-muted)]" aria-hidden />
          <Input
            id="models-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search models"
            className="h-10 bg-[color:var(--g-surface-1)] pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter models">
          <FilterChip active={filter === "all"} onClick={() => setFilter("all")}>
            All · {counts.all}
          </FilterChip>
          <FilterChip active={filter === "production"} onClick={() => setFilter("production")}>
            In production · {counts.production}
          </FilterChip>
          <FilterChip active={filter === "registered"} onClick={() => setFilter("registered")}>
            Registered · {counts.registered}
          </FilterChip>
          {builtInItems.length > 0 ? (
            <Link
              href="#built-in"
              className="inline-flex min-h-9 items-center rounded-full border border-dashed border-[color:var(--g-border-default)] px-3.5 text-[13px] text-[color:var(--g-text-secondary)] hover:border-[color:var(--g-border-strong)] hover:text-[color:var(--g-text-primary)]"
            >
              Built-in · {builtInItems.length}
            </Link>
          ) : null}
        </div>
        <span className="hidden flex-1 sm:block" aria-hidden />
        <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 text-[13px] text-[color:var(--g-text-secondary)] md:min-h-0">
          <input
            type="checkbox"
            className="h-[18px] w-[18px] accent-[color:var(--g-brand-active)]"
            checked={showTechnical}
            onChange={(e) => setShowTechnical(e.target.checked)}
          />
          Show technical details
        </label>
      </div>

      <ModelUsageTopology rows={lineage} showTechnical={showTechnical} />

      {loadingFirst ? (
        <p className={TYPE.bodyMuted}>Loading models…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2" data-review-surface="models-cards">
          {models.length === 0 ? (
            <div className="lg:col-span-2">
              <EmptyState
                title="No models yet"
                description="Create a model in Model Studio. This page lists registered models only and never shows sample cards."
                action={onRegister ? { label: "Create in Model Studio", onClick: onRegister } : undefined}
              />
            </div>
          ) : visible.length === 0 ? (
            <p className={cn(TYPE.bodyMuted, "lg:col-span-2")}>No models match this search or filter.</p>
          ) : (
            visible.map((model) => (
              <BusinessModelCard
                key={model.id}
                model={model}
                detail={details[model.id]}
                jobs={jobs}
                datasetName={model.datasetId ? (datasetNames[model.datasetId] ?? null) : null}
                showTechnical={showTechnical}
                onRetrain={(m) => void handleRetrain(m)}
                retrainPending={retrainingId === model.id}
                onDeploy={(m) => void handleDeploy(m)}
                deployPending={deployingId === model.id}
              />
            ))
          )}
          {suggestion && filter === "all" && !query.trim() ? (
            <ModelSuggestionCard item={suggestion} onDismiss={dismissSuggestion} />
          ) : null}
        </div>
      )}
    </div>
  )
}
