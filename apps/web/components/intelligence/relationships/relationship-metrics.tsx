"use client"

import { GravitreMetric } from "@/components/gravitre/nodus-product/metric"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { Graph, TreeStructure, WarningCircle } from "@phosphor-icons/react"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

export function RelationshipMetrics({ workspace }: { workspace: RelationshipsWorkspaceState }) {
  const { metrics, graphSummaryLoading } = workspace

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <GravitreMetric
        label="Organization knowledge"
        value={metrics.seededNodes}
        hint="Entities you seeded by hand"
        icon={<TreeStructure className="h-4 w-4" weight="duotone" aria-hidden />}
      />
      <GravitreMetric
        label="Learned relationships"
        value={metrics.learnedRelationships}
        hint="Connections inferred over time"
        icon={<Graph className="h-4 w-4" weight="duotone" aria-hidden />}
      />
      <GravitreMetric
        label="Needs review"
        value={metrics.needsReview}
        hint="Low confidence or thin evidence"
        warning={metrics.needsReview > 0}
        icon={<WarningCircle className="h-4 w-4" weight="duotone" aria-hidden />}
      />
      <GravitreMetric
        label="New this week"
        value={metrics.newThisWeek}
        hint={
          graphSummaryLoading
            ? "Loading graph summary…"
            : metrics.avgConfidence > 0
              ? `Avg confidence ${metrics.avgConfidence.toFixed(2)} (est.)`
              : "Recently observed links"
        }
        icon={<NucleoIntelligence className="h-4 w-4" aria-hidden />}
      />
    </div>
  )
}
