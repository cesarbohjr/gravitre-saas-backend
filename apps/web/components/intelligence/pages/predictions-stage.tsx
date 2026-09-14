"use client"

/**
 * I6 — Predictions hub: business cards + risk/opportunity topology.
 */
import { useMemo, useState } from "react"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { BusinessPredictionCard } from "@/components/intelligence/business-prediction-card"
import { PredictionRiskOpportunityTopology } from "@/components/intelligence/prediction-risk-opportunity-topology"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import type { IntelligencePageContextResponse } from "@/lib/api"
import {
  filterPredictionsByDepartment,
  formatPredictions,
} from "@/lib/intelligence/prediction-display"
import { qualityFlagToCopy } from "@/lib/intelligence/quality-copy"
import { readNumber } from "@/lib/intelligence/helpers"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { WarningCircle } from "@phosphor-icons/react"

const DEPARTMENTS = [
  { id: "all", label: "All departments" },
  { id: "sales", label: "Sales" },
  { id: "support", label: "Support" },
  { id: "operations", label: "Operations" },
  { id: "finance", label: "Finance" },
  { id: "marketing", label: "Marketing" },
  { id: "customer_success", label: "Customer success" },
] as const

export function PredictionsStage({
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
  const [department, setDepartment] = useState<string>("all")
  const metricsReady = isSnapshotMetricsReady(loadState)
  const isLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"

  const allPredictions = useMemo(
    () => formatPredictions(pageContext?.snapshot.predictions as Record<string, unknown>[] | undefined),
    [pageContext?.snapshot.predictions],
  )
  const predictions = useMemo(
    () => filterPredictionsByDepartment(allPredictions, department),
    [allPredictions, department],
  )

  const predictionMetrics =
    pageContext?.metrics.predictions ?? pageContext?.snapshot.metrics.predictions ?? {}
  const activeCount = metricsReady
    ? readNumber(predictionMetrics.activePredictions, predictions.length)
    : null
  const highPriority = metricsReady
    ? readNumber(predictionMetrics.highPriorityPredictions, null)
    : null
  const needsEvidence = metricsReady
    ? readNumber(predictionMetrics.predictionsNeedingEvidence, null)
    : null

  const hasUnscoped =
    pageContext?.qualityFlags?.includes("UNSCOPED_PREDICTION") ||
    allPredictions.some((row) => row.isUnscoped)

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-3">
        <GravitreMetric
          label="Active predictions"
          value={activeCount ?? "—"}
          hint={isLoading ? "Loading intelligence…" : "Deduped business signals"}
        />
        <GravitreMetric
          label="High priority"
          value={highPriority ?? "—"}
          hint={isLoading ? "Loading intelligence…" : "Confidence ≥ 65%"}
        />
        <GravitreMetric
          label="Need evidence"
          value={needsEvidence ?? "—"}
          hint={isLoading ? "Loading intelligence…" : "Unscoped or missing proof"}
          className="col-span-2 lg:col-span-1"
        />
      </section>

      {hasUnscoped ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-[var(--np-radius-md)] border border-amber-500/30 bg-amber-500/10 px-4 py-3"
        >
          <WarningCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" weight="duotone" />
          <div>
            <p className="text-sm font-medium text-foreground">
              {qualityFlagToCopy("UNSCOPED_PREDICTION")}
            </p>
            <p className={cn(TYPE.meta, "mt-0.5")}>
              Some predictions need a connected data source before Gravitre can scope them to your org.
            </p>
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className={TYPE.eyebrow}>Department</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>Filter prediction cards by department</p>
        </div>
        <Select value={department} onValueChange={setDepartment}>
          <SelectTrigger className="w-full sm:w-52" aria-label="Filter by department">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DEPARTMENTS.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <PredictionRiskOpportunityTopology predictions={predictions} />

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading predictions…</p>
      ) : predictions.length === 0 ? (
        <EmptyState
          variant="ai"
          title="No predictions in this view"
          description="Business predictions appear when Gravitre collects forward-looking signals from your connected sources."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {predictions.map((prediction) => (
            <BusinessPredictionCard key={prediction.id} prediction={prediction} />
          ))}
        </div>
      )}

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
