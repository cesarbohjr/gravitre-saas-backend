"use client"

/**
 * Impact (route /intelligence/performance): how sure each number is → from
 * spend to value → by agent → first measured result → latest outcome.
 * Real instrumentation only; unknown stays "—", never zero.
 */
import { useMemo } from "react"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { AgentRoiReport, Connector } from "@/types/api"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { ByAgentTable } from "@/components/intelligence/impact/by-agent-table"
import { CertaintyLegend } from "@/components/intelligence/impact/certainty"
import { FirstResultChecklist } from "@/components/intelligence/impact/first-result-checklist"
import {
  firstResultSteps,
  impactTotals,
  type ImpactPeriod,
} from "@/components/intelligence/impact/impact-model"
import { LatestOutcomeCard } from "@/components/intelligence/impact/latest-outcome-card"
import { SpendToValueFlow } from "@/components/intelligence/impact/spend-to-value"
import { APP_ROUTES } from "@/lib/app-routes"
import { readNumber } from "@/lib/intelligence/helpers"
import { pickPrimaryOutcomePath } from "@/lib/intelligence/performance-display"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"

export function PerformanceStage({
  pageContext,
  loadState,
  period,
  roi,
  roiLoading,
  connectors,
  connectorsLoading,
}: {
  pageContext?: IntelligencePageContextResponse | null
  loadState: SnapshotLoadState
  period: ImpactPeriod
  roi?: AgentRoiReport | null
  roiLoading: boolean
  connectors?: Connector[] | null
  connectorsLoading: boolean
}) {
  const metricsReady = isSnapshotMetricsReady(loadState)
  const snapshotLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"

  const paths = useMemo(() => pageContext?.outcomePaths ?? [], [pageContext?.outcomePaths])
  const latestPath = useMemo(() => pickPrimaryOutcomePath(paths), [paths])
  usePublishGravitreAISelection(
    latestPath ? { kind: "outcome_path", id: latestPath.id, label: latestPath.scopeLabel } : null,
  )

  const execMetrics = pageContext?.metrics.execution ?? pageContext?.snapshot.metrics.execution ?? {}
  const runningNow = metricsReady ? readNumber(execMetrics.runningWorkflows, null) : null

  const totals = useMemo(() => impactTotals(roi), [roi])
  const steps = useMemo(
    () =>
      firstResultSteps({
        connectors,
        totals,
        routes: { connectors: APP_ROUTES.connectors, plays: APP_ROUTES.plays, agents: APP_ROUTES.agents },
      }),
    [connectors, totals],
  )
  const roiPending = roiLoading && !roi

  return (
    <div className="space-y-6 pt-2">
      <CertaintyLegend />

      <SpendToValueFlow totals={totals} loading={roiPending} runningNow={runningNow} />

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <ByAgentTable
          rows={roi?.agents ?? []}
          snapshotAgents={pageContext?.snapshot.agents ?? []}
          period={period}
          loading={roiPending}
        />
        <div className="space-y-6">
          <FirstResultChecklist steps={steps} loading={roiPending || (connectorsLoading && !connectors)} />
          <LatestOutcomeCard path={latestPath} loading={snapshotLoading} />
        </div>
      </div>
    </div>
  )
}
