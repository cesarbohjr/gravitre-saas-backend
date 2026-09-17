"use client"

/**
 * I7 — Performance: outcome attribution flow first, then view-mode contribution.
 */
import { useMemo, useState } from "react"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { SegmentedControl } from "@/components/gravitre/filter-chip"
import { AgentContributionCard } from "@/components/intelligence/agent-contribution-card"
import { OutcomeAttributionFlow } from "@/components/intelligence/outcome-attribution-flow"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import { enterpriseApi, type IntelligencePageContextResponse } from "@/lib/api"
import { readNumber } from "@/lib/intelligence/helpers"
import {
  PERFORMANCE_VIEW_MODES,
  pickPrimaryOutcomePath,
  roiMetricDisplay,
  type PerformanceViewMode,
} from "@/lib/intelligence/performance-display"
import { qualityFlagToCopy } from "@/lib/intelligence/quality-copy"
import { isSnapshotMetricsReady, type SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { AGENT_ROI_METHODOLOGY } from "@/lib/outcome-labels"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"

export function PerformanceStage({
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
  const [viewMode, setViewMode] = useState<PerformanceViewMode>("impact")
  const metricsReady = isSnapshotMetricsReady(loadState)
  const isLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"

  const paths = pageContext?.outcomePaths ?? []
  const [pathId, setPathId] = useState<string | null>(null)
  const primary = useMemo(() => pickPrimaryOutcomePath(paths), [paths])
  const selectedPathId = pathId && paths.some((p) => p.id === pathId) ? pathId : primary?.id
  const activePath = paths.find((p) => p.id === selectedPathId) ?? primary ?? null
  usePublishGravitreAISelection(
    activePath
      ? { kind: "outcome_path", id: activePath.id, label: activePath.scopeLabel }
      : null,
  )

  const { data: roi, isLoading: roiLoading } = useSWR(
    enabled ? ["intelligence/performance/agent-roi", 30] : null,
    () => enterpriseApi.getAgentRoi({ periodDays: 30 }),
    { revalidateOnFocus: false },
  )

  const outcomeMetrics = pageContext?.metrics.outcomes ?? pageContext?.snapshot.metrics.outcomes ?? {}
  const execMetrics = pageContext?.metrics.execution ?? pageContext?.snapshot.metrics.execution ?? {}
  const measuredOutcomes = metricsReady ? readNumber(outcomeMetrics.measuredOutcomes, null) : null
  const actionsCompleted = metricsReady ? readNumber(execMetrics.actionsCompleted, null) : null
  const runningWorkflows = metricsReady ? readNumber(execMetrics.runningWorkflows, null) : null

  const hoursSaved = roiMetricDisplay(roi?.orgTotals.estimatedHoursSaved)
  const agentCost = roiMetricDisplay(roi?.orgTotals.agentCostUsd)
  const tasks = roiMetricDisplay(roi?.orgTotals.tasksCompleted)
  const revenue = roiMetricDisplay(roi?.orgTotals.revenueInfluencedUsd)

  const hasNoAttribution =
    pageContext?.qualityFlags?.includes("NO_OUTCOME_ATTRIBUTION") ||
    (metricsReady && paths.every((p) => p.presentStepCount <= 1))

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div>
          <p className={TYPE.eyebrow}>Is Gravitre making the business better?</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Evidence-backed outcomes only. Unknown stays unknown — never a false zero.
          </p>
        </div>
        <SegmentedControl
          ariaLabel="Performance view"
          options={PERFORMANCE_VIEW_MODES}
          value={viewMode}
          onChange={setViewMode}
          className="w-full max-w-full flex-wrap sm:w-auto"
        />
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading outcome attribution…</p>
      ) : (
        <OutcomeAttributionFlow
          paths={paths}
          selectedPathId={selectedPathId}
          onPathChange={setPathId}
        />
      )}

      {hasNoAttribution && metricsReady ? (
        <p className={cn(TYPE.meta, "border-b border-divide py-2")}>
          {qualityFlagToCopy("NO_OUTCOME_ATTRIBUTION")}
        </p>
      ) : null}

      <details>
        <summary className="cursor-pointer list-none border-b border-divide py-2">
          <p className={TYPE.eyebrow}>Metrics</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>Totals for the selected view — after the path, not instead of it.</p>
        </summary>
      <div className="grid grid-cols-2 gap-[var(--np-kpi-gap)] py-4 lg:grid-cols-4">
        {viewMode === "impact" ? (
          <>
            <GravitreMetric
              label="Measured outcomes"
              value={measuredOutcomes ?? "—"}
              hint={isLoading ? "Loading intelligence…" : "Canonical IMPROVES window"}
            />
            <GravitreMetric
              label="Revenue influenced"
              value={roiLoading ? "—" : revenue.value}
              hint={roiLoading ? "Loading ROI…" : revenue.hint || "Verified monetary metadata only"}
            />
            <GravitreMetric
              label="Actions completed"
              value={actionsCompleted ?? "—"}
              hint={isLoading ? "Loading intelligence…" : "Attributed execution"}
            />
            <GravitreMetric
              label="Estimated hours saved"
              value={roiLoading ? "—" : hoursSaved.value}
              hint={roiLoading ? "Loading ROI…" : hoursSaved.hint}
            />
          </>
        ) : null}
        {viewMode === "efficiency" ? (
          <>
            <GravitreMetric
              label="Tasks completed"
              value={roiLoading ? "—" : tasks.value}
              hint={roiLoading ? "Loading ROI…" : tasks.hint || "Operational count"}
            />
            <GravitreMetric
              label="Estimated hours saved"
              value={roiLoading ? "—" : hoursSaved.value}
              hint={roiLoading ? "Loading ROI…" : hoursSaved.hint}
            />
          </>
        ) : null}
        {viewMode === "agents" ? (
          <>
            <GravitreMetric
              label="Actions completed"
              value={actionsCompleted ?? "—"}
              hint={isLoading ? "Loading intelligence…" : "Execution window"}
            />
            <GravitreMetric
              label="Estimated hours saved"
              value={roiLoading ? "—" : hoursSaved.value}
              hint={roiLoading ? "Loading ROI…" : hoursSaved.hint}
            />
          </>
        ) : null}
        {viewMode === "reliability" ? (
          <>
            <GravitreMetric
              label="Actions completed"
              value={actionsCompleted ?? "—"}
              hint={isLoading ? "Loading intelligence…" : "Execution window"}
            />
            <GravitreMetric
              label="Running workflows"
              value={runningWorkflows ?? "—"}
              hint={isLoading ? "Loading intelligence…" : "Live runs"}
            />
          </>
        ) : null}
        {viewMode === "cost" ? (
          <>
            <GravitreMetric
              label="Agent cost"
              value={roiLoading ? "—" : agentCost.value}
              hint={roiLoading ? "Loading ROI…" : agentCost.hint || "Measured model spend"}
            />
            <GravitreMetric
              label="Estimated hours saved"
              value={roiLoading ? "—" : hoursSaved.value}
              hint={roiLoading ? "Loading ROI…" : hoursSaved.hint}
            />
          </>
        ) : null}
      </div>
      </details>

      <div className="space-y-3">
        <div>
          <p className={TYPE.eyebrow}>Agent contribution</p>
          <p className={cn(TYPE.meta, "mt-0.5 max-w-3xl")}>{AGENT_ROI_METHODOLOGY}</p>
        </div>
        {roiLoading && !roi ? (
          <p className="text-sm text-muted-foreground">Loading agent contribution…</p>
        ) : !roi || roi.agents.length === 0 ? (
          <EmptyState
            title="No agent contribution in this period"
            description="Contribution cards appear when agents complete recorded work. Hours saved stay estimates until measured time-on-task exists."
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {roi.agents.map((agent) => (
              <AgentContributionCard key={agent.agentId} agent={agent} viewMode={viewMode} />
            ))}
          </div>
        )}
      </div>

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
