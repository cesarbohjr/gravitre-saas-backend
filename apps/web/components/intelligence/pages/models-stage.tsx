"use client"

/**
 * I8 — Models catalog: business view first, technical toggle, usage topology.
 */
import { useMemo, useState } from "react"
import Link from "next/link"
import { EmptyState } from "@/components/gravitre/empty-state"
import { BusinessModelsList } from "@/components/intelligence/business-model-card"
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
          <p className={cn(TYPE.meta, "mt-0.5")}>
            What each model does, whether it is in use, and where.
          </p>
        </div>
        <label className={cn(TYPE.meta, "inline-flex min-h-11 cursor-pointer items-center gap-2 md:min-h-0")}>
          <input
            type="checkbox"
            className="h-4 w-4 accent-[color:var(--g-brand)]"
            checked={view === "technical"}
            onChange={(e) => setView(e.target.checked ? "technical" : "business")}
          />
          Show technical details
        </label>
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
        <BusinessModelsList models={catalog} view={view} />
      )}

      <p className={cn(TYPE.meta, "text-pretty")}>
        Create, evaluate, deploy, and inspect runs in{" "}
        <Link href={APP_ROUTES.intelligenceModelStudio} className="font-medium text-[color:var(--g-brand-active)] hover:underline dark:text-[color:var(--g-brand)]">
          Model Studio
        </Link>
        , where you can also train them.
      </p>

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
