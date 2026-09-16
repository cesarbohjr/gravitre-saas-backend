"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { roiMetricDisplay } from "@/lib/intelligence/performance-display"
import type { PerformanceViewMode } from "@/lib/intelligence/performance-display"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { AgentRoiRow } from "@/types/api"

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

function metricsForView(agent: AgentRoiRow, viewMode: PerformanceViewMode) {
  switch (viewMode) {
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
