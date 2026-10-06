"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { roiMetricDisplay } from "@/lib/intelligence/performance-display"
import type { PerformanceViewMode } from "@/lib/intelligence/performance-display"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { AgentRoiRow } from "@/types/api"

type ContributionView = PerformanceViewMode | "all"

export function AgentContributionRow({
  agent,
  viewMode = "all",
}: {
  agent: AgentRoiRow
  viewMode?: ContributionView
}) {
  const metrics = metricsForView(agent, viewMode)
  return (
    <div
      data-testid="agent-contribution-row"
      className={cn(
        "grid grid-cols-2 gap-3 py-3",
        metrics.length >= 4
          ? "sm:grid-cols-[minmax(8rem,1.4fr)_repeat(4,minmax(0,1fr))]"
          : "sm:grid-cols-[minmax(8rem,1fr)_repeat(3,minmax(0,1fr))]",
      )}
    >
      <p className="col-span-2 text-sm font-medium text-foreground sm:col-span-1">{agent.agentName}</p>
      {metrics.map((metric) => {
        const display = roiMetricDisplay(metric)
        return (
          <div key={metric.label}>
            <p className={TYPE.eyebrow}>{metric.label}</p>
            <p className={cn("mt-0.5 text-sm tabular-nums", display.unknown && "text-muted-foreground")}>
              {display.value}
            </p>
            {display.hint ? <p className={cn(TYPE.meta, "mt-0.5")}>{display.hint}</p> : null}
          </div>
        )
      })}
    </div>
  )
}

export function AgentContributionCard({
  agent,
  viewMode,
}: {
  agent: AgentRoiRow
  viewMode: PerformanceViewMode
}) {
  const metrics = metricsForView(agent, viewMode)
  return (
    <Card data-testid="agent-contribution-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">{agent.agentName}</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3">
        {metrics.map((metric) => {
          const display = roiMetricDisplay(metric)
          return (
            <div key={metric.label}>
              <p className={TYPE.eyebrow}>{metric.label}</p>
              <p className={cn("mt-0.5 text-sm font-semibold tabular-nums", display.unknown && "text-muted-foreground")}>
                {display.value}
              </p>
              {display.hint ? <p className={cn(TYPE.meta, "mt-0.5")}>{display.hint}</p> : null}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

function metricsForView(agent: AgentRoiRow, viewMode: ContributionView) {
  switch (viewMode) {
    case "all":
      return [
        agent.tasksCompleted,
        agent.estimatedHoursSaved,
        agent.revenueInfluencedUsd,
        agent.agentCostUsd,
      ]
    case "efficiency":
      return [agent.tasksCompleted, agent.estimatedHoursSaved]
    case "cost":
      return [agent.agentCostUsd, agent.estimatedLaborValueUsd]
    case "reliability":
      return [agent.tasksCompleted, agent.actionsExecuted]
    case "agents":
      return [agent.actionsExecuted, agent.estimatedHoursSaved, agent.revenueInfluencedUsd]
    default:
      return [agent.actionsExecuted, agent.revenueInfluencedUsd, agent.estimatedHoursSaved]
  }
}
