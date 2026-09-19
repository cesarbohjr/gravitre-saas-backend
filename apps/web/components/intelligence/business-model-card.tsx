"use client"

import { useState } from "react"
import Link from "next/link"
import { ModelStatusBadge } from "@/components/intelligence/model-status-badge"
import type { ModelCatalogDisplay, ModelCatalogView } from "@/lib/intelligence/model-catalog-display"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function BusinessModelInspector({
  model,
  view,
}: {
  model: ModelCatalogDisplay
  view: ModelCatalogView
}) {
  return (
    <div className="space-y-3 p-4" data-review-surface="models-inspect" data-testid="business-model-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-medium leading-snug text-foreground">{model.name}</h2>
          <p className={cn(TYPE.meta, "mt-1")}>{model.purpose}</p>
        </div>
        <ModelStatusBadge status={model.technicalStatus} size="sm" showDetail={false} />
      </div>
      {view === "business" ? (
        <>
          <p className="text-sm text-muted-foreground">
            <span className={TYPE.eyebrow}>Status: </span>
            {model.businessStatus}
          </p>
          <p className="text-sm text-muted-foreground">
            <span className={TYPE.eyebrow}>Where used: </span>
            {model.whereUsed}
          </p>
          <p className="text-sm text-muted-foreground">
            <span className={TYPE.eyebrow}>Performance: </span>
            {model.performance}
          </p>
          {model.learningSources.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              <span className={TYPE.eyebrow}>Learning sources: </span>
              {model.learningSources.join(" · ")}
            </p>
          ) : null}
          {model.lastUpdatedLabel ? (
            <p className="text-sm text-muted-foreground">
              <span className={TYPE.eyebrow}>Last updated: </span>
              {model.lastUpdatedLabel}
            </p>
          ) : null}
          <p className={cn(TYPE.meta, "border-t border-divide pt-2")}>{model.recommendedImprovement}</p>
        </>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            <span className={TYPE.eyebrow}>Architecture: </span>
            {model.architecture}
          </p>
          {model.baseModel ? (
            <p className="font-mono text-xs text-muted-foreground">
              <span className={TYPE.eyebrow}>Base: </span>
              {model.baseModel}
            </p>
          ) : null}
          {model.datasetId ? (
            <p className="font-mono text-xs text-muted-foreground">
              <span className={TYPE.eyebrow}>Dataset: </span>
              {model.datasetId}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              <span className={TYPE.eyebrow}>Datasets: </span>
              Not linked yet
            </p>
          )}
          <p className="text-sm text-muted-foreground">
            <span className={TYPE.eyebrow}>Version: </span>
            {model.versionLabel}
          </p>
          <p className={cn(TYPE.meta, "border-t border-divide pt-2")}>
            Hyperparameters, drift, and run logs live on the model detail page — this catalog does
            not invent those fields.
          </p>
        </>
      )}
      <Link
        href={model.href}
        data-review-cta="open-model"
        className="inline-flex text-sm font-medium text-[color:var(--g-brand)] hover:underline"
      >
        Open model
      </Link>
    </div>
  )
}

/** Inspector body — name kept for existing tests/imports. */
export function BusinessModelCard({
  model,
  view,
}: {
  model: ModelCatalogDisplay
  view: ModelCatalogView
}) {
  return <BusinessModelInspector model={model} view={view} />
}

export function BusinessModelsList({
  models,
  view,
}: {
  models: ModelCatalogDisplay[]
  view: ModelCatalogView
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = models.find((model) => model.id === selectedId) ?? null

  return (
    <div className="flex flex-col border border-divide lg:flex-row">
      <ul className="min-w-0 flex-1 divide-y divide-divide" data-review-surface="models-queue">
        {models.map((model) => {
          const isSelected = selectedId === model.id
          return (
            <li key={model.id}>
              <button
                type="button"
                onClick={() => setSelectedId(model.id)}
                className={cn(
                  "flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left",
                  isSelected
                    ? "bg-[color:var(--g-surface-2)]"
                    : "hover:bg-[color:var(--g-surface-2)]/50",
                )}
              >
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-foreground">{model.name}</span>
                  <span className={cn(TYPE.meta, "mt-0.5 block")}>
                    {view === "business" ? model.businessStatus : model.architecture}
                    {model.lastUpdatedLabel ? ` · ${model.lastUpdatedLabel}` : ""}
                  </span>
                </span>
                <ModelStatusBadge status={model.technicalStatus} size="sm" showDetail={false} />
              </button>
            </li>
          )
        })}
      </ul>
      {selected ? (
        <div className="flex-1 border-t border-divide bg-[color:var(--g-canvas)] lg:border-t-0 lg:border-l">
          <BusinessModelInspector model={selected} view={view} />
        </div>
      ) : (
        <p className="sr-only">Select a model — inspector stays closed until then.</p>
      )}
    </div>
  )
}
