"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/gravitre/empty-state"
import { formatPercent, readString } from "@/lib/intelligence/helpers"
import type { Agent } from "@/types/api"
import { CheckCircle, XCircle } from "@phosphor-icons/react"

export function OutcomesTab({
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
    return <div className="text-sm text-muted-foreground">Loading outcomes…</div>
  }

  const agentSuccessRates = (evaluationsData?.agent_success_rates as Record<string, Record<string, unknown>> | undefined) ?? {}
  const successEntry = agentSuccessRates[agent.id]
  const recentEvents = (outcomesData?.recent_events as Array<Record<string, unknown>> | undefined) ?? []
  const agentEvents = recentEvents.filter(
    (row) =>
      (row.entity_type === "agent" && row.entity_id === agent.id) ||
      row.agent_id === agent.id ||
      row.recommendation_id,
  )

  if (successEntry?.status === "insufficient_data" && agentEvents.length === 0) {
    return (
      <EmptyState
        title="Not enough outcome data yet"
        description="This grows as the agent completes more tasks with measurable results."
      />
    )
  }

  const successScore = successEntry?.status === "ok" ? Number(successEntry.score) : null

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Business outcome score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{successScore != null ? formatPercent(successScore) : "—"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Events recorded</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{agentEvents.length}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Outcome timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {agentEvents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No timeline events for this agent yet.</p>
          ) : (
            <div className="ml-3 space-y-4 border-l-2 border-border pl-4">
              {agentEvents.map((event, idx) => {
                const eventName = readString(event.outcome_event, "event")
                const positive = eventName.includes("approved") || eventName.includes("executed")
                return (
                  <div key={String(event.id ?? idx)} className="relative">
                    <span className="absolute -left-[25px] flex h-5 w-5 items-center justify-center rounded-full bg-background">
                      {positive ? (
                        <CheckCircle weight="fill" className="h-5 w-5 text-success" aria-hidden />
                      ) : (
                        <XCircle weight="fill" className="h-5 w-5 text-destructive" aria-hidden />
                      )}
                    </span>
                    <p className="text-sm font-medium capitalize text-foreground">
                      {eventName.replace(/_/g, " ")}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {readString(event.created_at, "—")}
                    </p>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
