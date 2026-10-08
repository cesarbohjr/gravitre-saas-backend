"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { IntelligenceSparkline } from "@/components/intelligence/intelligence-sparkline"
import { formatPercent, readNumber } from "@/lib/intelligence/helpers"
import type { Agent } from "@/types/api"

export function PerformanceTab({
  agent,
  evaluationsData,
  outcomesData,
  isLoading,
  enabled,
}: {
  agent: Agent
  evaluationsData?: Record<string, unknown>
  outcomesData?: Record<string, unknown>
  isLoading: boolean
  enabled: boolean
}) {
  if (!enabled) return null

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Loading performance data…</div>
  }

  const agentSuccessRates = (evaluationsData?.agent_success_rates as Record<string, Record<string, unknown>> | undefined) ?? {}
  const successEntry = agentSuccessRates[agent.id]
  const successScore = successEntry?.status === "ok" ? Number(successEntry.score) : null

  const recentEvents = (outcomesData?.recent_events as Array<Record<string, unknown>> | undefined) ?? []
  const sparklineData = recentEvents
    .filter((row) => row.agent_id === agent.id || row.entity_id === agent.id)
    .slice(0, 14)
    .map((row, index) => ({ day: index, value: Number(row.confidence_score ?? 0) }))
    .filter((row) => row.value > 0)

  const byEventType = (outcomesData?.by_event_type as Record<string, number> | undefined) ?? {}
  const approved = readNumber(byEventType.recommendation_approved)
  const rejected = readNumber(byEventType.recommendation_rejected)

  const agentEvents = recentEvents.filter(
    (row) => row.entity_type === "agent" && row.entity_id === agent.id,
  )
  const actionsExecuted = agentEvents.filter((row) =>
    ["workflow_executed", "connector_action_executed", "recommendation_approved"].includes(
      String(row.outcome_event ?? ""),
    ),
  ).length

  const taskTypeCounts = agentEvents.reduce<Record<string, number>>((acc, row) => {
    const metadata = row.metadata as Record<string, unknown> | undefined
    const type = String(metadata?.task_type ?? row.task_type ?? "unknown")
    acc[type] = (acc[type] ?? 0) + 1
    return acc
  }, {})

  const topTaskTypes = Object.entries(taskTypeCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Success rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{successScore != null ? formatPercent(successScore) : "—"}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Confidence trend</CardTitle>
          </CardHeader>
          <CardContent>
            {sparklineData.length > 0 ? (
              <IntelligenceSparkline data={sparklineData} />
            ) : (
              <div className="text-2xl font-bold text-muted-foreground">—</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {approved}{" "}
              <span className="text-sm font-normal text-muted-foreground">approved</span>
            </div>
            <div className="text-sm text-muted-foreground">{rejected} rejected</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Actions executed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{actionsExecuted}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top task types</CardTitle>
        </CardHeader>
        <CardContent>
          {topTaskTypes.length > 0 ? (
            <div className="space-y-4">
              {topTaskTypes.map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <span className="text-sm font-medium capitalize">{type.replace(/_/g, " ")}</span>
                  <span className="text-sm text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No recent tasks found for this agent.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
