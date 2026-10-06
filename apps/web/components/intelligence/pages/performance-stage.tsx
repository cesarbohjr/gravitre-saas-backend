"use client"

/**
 * Impact (route /intelligence/performance): totals → per-agent table → how one
 * outcome happened. Real instrumentation only; unknown stays "—", never zero.
 */
import { useMemo, useState } from "react"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { AgentContributionRow } from "@/components/intelligence/agent-contribution-card"
import { OutcomeAttributionFlow } from "@/components/intelligence/outcome-attribution-flow"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import { enterpriseApi, type IntelligencePageContextResponse } from "@/lib/api"
import { readNumber } from "@/lib/intelligence/helpers"
import {
  outcomeHeadline,
  pickPrimaryOutcomePath,
  roiMetricDisplay,
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

  const roiTotals = roi?.orgTotals
  const roiAgents = roi?.agents ?? []
  const hoursSaved = roiMetricDisplay(roiTotals?.estimatedHoursSaved)
  const agentCost = roiMetricDisplay(roiTotals?.agentCostUsd)
  const tasks = roiMetricDisplay(roiTotals?.tasksCompleted)
  const revenue = roiMetricDisplay(roiTotals?.revenueInfluencedUsd)

  const hasNoAttribution =
    pageContext?.qualityFlags?.includes("NO_OUTCOME_ATTRIBUTION") ||
    (metricsReady && paths.every((p) => p.presentStepCount <= 1))

  const headline = outcomeHeadline(activePath)

  return (
    <div className="space-y-8">
      {/*
        One level of navigation: no view switcher. Every total for the window is
        visible at once, then the per-agent table, then how one outcome happened.
      */}
      <section aria-labelledby="impact-totals-heading" className="space-y-3">
        <div>
          <p id="impact-totals-heading" className={TYPE.eyebrow}>Last 30 days</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Totals across all agents. A dash means Gravitre has no evidence yet, never zero.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-[var(--np-kpi-gap)] md:grid-cols-3 xl:grid-cols-6">
          <GravitreMetric
            label="Measured outcomes"
            value={measuredOutcomes ?? "—"}
            hint={isLoading ? "Loading…" : "Results with evidence"}
          />
          <GravitreMetric
            label="Revenue influenced"
            value={roiLoading ? "—" : revenue.value}
            hint={roiLoading ? "Loading…" : revenue.hint || "Verified amounts only"}
          />
          <GravitreMetric
            label="Hours saved"
            value={roiLoading ? "—" : hoursSaved.value}
            hint={roiLoading ? "Loading…" : hoursSaved.hint || "Estimate"}
          />
          <GravitreMetric
            label="Tasks completed"
            value={roiLoading ? "—" : tasks.value}
            hint={roiLoading ? "Loading…" : tasks.hint || "Finished agent work"}
          />
          <GravitreMetric
            label="Agent cost"
            value={roiLoading ? "—" : agentCost.value}
            hint={roiLoading ? "Loading…" : agentCost.hint || "Model spend"}
          />
          <GravitreMetric
            label="Running now"
            value={runningWorkflows ?? "—"}
            hint={
              isLoading
                ? "Loading…"
                : actionsCompleted != null
                  ? `${actionsCompleted} actions completed`
                  : "Live workflow runs"
            }
          />
        </div>
      </section>

      <div className="space-y-3">
        <div>
          <p className={TYPE.eyebrow}>By agent</p>
          <p className={cn(TYPE.meta, "mt-0.5 max-w-3xl")}>{AGENT_ROI_METHODOLOGY}</p>
        </div>
        {roiLoading && !roi ? (
          <p className="text-sm text-muted-foreground">Loading agent contribution…</p>
        ) : roiAgents.length === 0 ? (
          <EmptyState
            title="No agent contribution in this period"
            description="Rows appear when agents complete recorded work. Hours saved stay estimates until measured time-on-task exists."
          />
        ) : (
          <div className="divide-y divide-[color:var(--g-border-default)] border-y border-[color:var(--g-border-default)]">
            {roiAgents.map((agent) => (
              <AgentContributionRow key={agent.agentId} agent={agent} />
            ))}
          </div>
        )}
      </div>

      <section aria-labelledby="impact-outcome-heading" className="space-y-3">
        <div>
          <p id="impact-outcome-heading" className={TYPE.eyebrow}>Outcome</p>
          <h2 className={cn(TYPE.sectionTitle, "mt-1 text-pretty")}>
            {isLoading
              ? "Loading outcome…"
              : headline ?? "No measured outcome in this window"}
          </h2>
          <p className={cn(TYPE.meta, "mt-1")}>
            How the most complete recent outcome came about, step by step. Only steps with evidence are shown.
          </p>
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading outcome steps…</p>
        ) : (
          <OutcomeAttributionFlow
            paths={paths}
            selectedPathId={selectedPathId}
            onPathChange={setPathId}
          />
        )}

        {hasNoAttribution && metricsReady && paths.length > 0 ? (
          <p className={cn(TYPE.meta, "border-b border-divide py-2")}>
            {qualityFlagToCopy("NO_OUTCOME_ATTRIBUTION")}
          </p>
        ) : null}
      </section>

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
