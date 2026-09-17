"use client"

/**
 * I8 — Models catalog: business view first, technical toggle, usage topology.
 */
import { useMemo, useState } from "react"
import Link from "next/link"
import { EmptyState } from "@/components/gravitre/empty-state"
import { BusinessModelCard } from "@/components/intelligence/business-model-card"
import { ModelUsageTopology } from "@/components/intelligence/model-usage-topology"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  formatModelCatalogRow,
  type ModelCatalogView,
} from "@/lib/intelligence/model-catalog-display"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { MlModelSummary } from "@/types/api"

const VIEW_OPTIONS: { id: ModelCatalogView; label: string }[] = [
  { id: "business", label: "Business view" },
  { id: "technical", label: "Technical view" },
]

export function ModelsStage({
  models,
  isLoading,
  enabled,
  suggestedQuestions,
  onRegister,
}: {
  models: MlModelSummary[]
  isLoading: boolean
  enabled: boolean
  suggestedQuestions?: string[]
  onRegister?: () => void
}) {
  const [view, setView] = useState<ModelCatalogView>("business")
  const catalog = useMemo(() => models.map(formatModelCatalogRow), [models])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={TYPE.eyebrow}>Catalog</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Purpose, business status, and where models are used — not an engineering registry dump.
          </p>
        </div>
        <nav aria-label="Models view" className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          {VIEW_OPTIONS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setView(item.id)}
              className={cn(
                TYPE.meta,
                "underline-offset-4",
                view === item.id
                  ? "text-[color:var(--g-text-primary)] underline"
                  : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
              )}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      <ModelUsageTopology models={catalog} />

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading models…</p>
      ) : catalog.length === 0 ? (
        <EmptyState
          title="No models yet"
          description="Create a model in Model Studio. This catalog lists registered models only — it does not invent sample cards."
          action={
            onRegister
              ? { label: "Create in Model Studio", onClick: onRegister }
              : undefined
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {catalog.map((model) => (
            <BusinessModelCard key={model.id} model={model} view={view} />
          ))}
        </div>
      )}

      <p className={cn(TYPE.meta, "text-pretty")}>
        Create, train, evaluate, deploy, and inspect runs in{" "}
        <Link href={APP_ROUTES.intelligenceModelStudio} className="font-medium text-[color:var(--g-brand)] hover:underline">
          Model Studio
        </Link>
        . Training is folded there — not a separate hub tab.
      </p>

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
