"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ModelStatusBadge } from "@/components/intelligence/model-status-badge"
import type { ModelCatalogDisplay, ModelCatalogView } from "@/lib/intelligence/model-catalog-display"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function BusinessModelCard({
  model,
  view,
}: {
  model: ModelCatalogDisplay
  view: ModelCatalogView
}) {
  return (
    <Card data-testid="business-model-card">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base font-medium leading-snug">{model.name}</CardTitle>
            <p className={cn(TYPE.meta, "mt-1")}>{model.purpose}</p>
          </div>
          <ModelStatusBadge status={model.technicalStatus} size="sm" showDetail={false} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        {view === "business" ? (
          <>
            <p>
              <span className={TYPE.eyebrow}>Status: </span>
              {model.businessStatus}
            </p>
            <p>
              <span className={TYPE.eyebrow}>Where used: </span>
              {model.whereUsed}
            </p>
            <p>
              <span className={TYPE.eyebrow}>Performance: </span>
              {model.performance}
            </p>
            {model.learningSources.length > 0 ? (
              <p>
                <span className={TYPE.eyebrow}>Learning sources: </span>
                {model.learningSources.join(" · ")}
              </p>
            ) : null}
            {model.lastUpdatedLabel ? (
              <p>
                <span className={TYPE.eyebrow}>Last updated: </span>
                {model.lastUpdatedLabel}
              </p>
            ) : null}
            <p className={cn(TYPE.meta, "border-t border-divide pt-2")}>{model.recommendedImprovement}</p>
          </>
        ) : (
          <>
            <p>
              <span className={TYPE.eyebrow}>Architecture: </span>
              {model.architecture}
            </p>
            {model.baseModel ? (
              <p className="font-mono text-xs">
                <span className={TYPE.eyebrow}>Base: </span>
                {model.baseModel}
              </p>
            ) : null}
            {model.datasetId ? (
              <p className="font-mono text-xs">
                <span className={TYPE.eyebrow}>Dataset: </span>
                {model.datasetId}
              </p>
            ) : (
              <p>
                <span className={TYPE.eyebrow}>Datasets: </span>
                Not linked yet
              </p>
            )}
            <p>
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
          className="inline-flex text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Open model
        </Link>
      </CardContent>
    </Card>
  )
}
