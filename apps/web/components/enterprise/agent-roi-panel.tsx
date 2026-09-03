"use client"

import useSWR from "swr"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { enterpriseApi } from "@/lib/api"
import type { AgentRoiMetric, AgentRoiProvenance, AgentRoiReport } from "@/types/api"
import { MetricProvenanceBadge } from "@/components/outcome/metric-provenance-badge"
import type { OutcomeMeasurementKind } from "@/lib/outcome-labels"
import { AGENT_ROI_METHODOLOGY } from "@/lib/outcome-labels"
import { cn } from "@/lib/utils"
import { useState } from "react"

function formatMetric(metric: AgentRoiMetric | undefined): string {
  if (!metric || metric.value == null || metric.value === "") return "—"
  const num = typeof metric.value === "number" ? metric.value : Number(metric.value)
  if (Number.isNaN(num)) return String(metric.value)
  if (metric.unit === "usd") {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: num >= 100 ? 0 : 2,
    }).format(num)
  }
  if (metric.unit === "hours") return `${num.toFixed(num >= 10 ? 1 : 2)} h`
  if (metric.unit === "x") return `${num.toFixed(2)}×`
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(num)
}

function badgeKind(provenance: AgentRoiProvenance | string | undefined): OutcomeMeasurementKind | null {
  if (provenance === "estimate") return "estimate"
  if (provenance === "operational") return "operational"
  if (provenance === "measured") return "measured"
  return null
}

function MetricCell({ metric }: { metric: AgentRoiMetric }) {
  const kind = badgeKind(metric.provenance)
  const muted =
    metric.provenance === "not_configured" || metric.provenance === "insufficient_data"
  return (
    <div className={cn("space-y-1", muted && "opacity-80")}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {metric.label}
        </span>
        {kind ? <MetricProvenanceBadge kind={kind} /> : null}
        {muted ? (
          <span className="text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-400">
            {metric.provenance}
          </span>
        ) : null}
      </div>
      <p className="text-lg font-semibold tabular-nums text-foreground">{formatMetric(metric)}</p>
      {metric.note ? <p className="text-[11px] text-muted-foreground text-pretty">{metric.note}</p> : null}
    </div>
  )
}

export function AgentRoiPanel({
  agentId,
  defaultPeriodDays = 30,
  compact = false,
}: {
  agentId?: string
  defaultPeriodDays?: number
  compact?: boolean
}) {
  const [periodDays, setPeriodDays] = useState(defaultPeriodDays)
  const { data, error, isLoading } = useSWR<AgentRoiReport>(
    ["enterprise/agent-roi", periodDays, agentId ?? "org"],
    () => enterpriseApi.getAgentRoi({ periodDays, agentId }),
    { revalidateOnFocus: false },
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl space-y-1">
          <h3 className="text-sm font-semibold text-foreground">
            {agentId ? "Agent ROI" : "Organization agent ROI"}
          </h3>
          <p className="text-xs text-muted-foreground text-pretty">{AGENT_ROI_METHODOLOGY}</p>
        </div>
        <Select value={String(periodDays)} onValueChange={(v) => setPeriodDays(Number(v))}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Period" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading && !data ? (
        <p className="text-sm text-muted-foreground">Loading agent ROI…</p>
      ) : null}
      {error ? (
        <p className="text-sm text-destructive">Unable to load agent ROI. Try again.</p>
      ) : null}

      {data ? (
        <>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Org totals</CardTitle>
              <CardDescription>
                {data.periodStart.slice(0, 10)} → {data.periodEnd.slice(0, 10)} · labor rate $
                {data.laborUsdPerHour.value}/hr ({data.laborUsdPerHour.source}
                {data.laborUsdPerHour.provenance === "estimate" ? " — estimate default" : ""})
              </CardDescription>
            </CardHeader>
            <CardContent
              className={cn(
                "grid gap-4",
                compact ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
              )}
            >
              <MetricCell metric={data.orgTotals.tasksCompleted} />
              <MetricCell metric={data.orgTotals.actionsExecuted} />
              <MetricCell metric={data.orgTotals.agentCostUsd} />
              <MetricCell metric={data.orgTotals.estimatedHoursSaved} />
              <MetricCell metric={data.orgTotals.estimatedLaborValueUsd} />
              <MetricCell metric={data.orgTotals.revenueInfluencedUsd} />
              <MetricCell metric={data.orgTotals.roiMultiple} />
            </CardContent>
          </Card>

          {!agentId ? (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-foreground">Per agent</h4>
              {data.agents.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No agent activity in this period (no completed jobs or measured model spend).
                </p>
              ) : (
                data.agents.map((agent) => (
                  <Card key={agent.agentId}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">{agent.agentName}</CardTitle>
                      <CardDescription className="font-mono text-[11px]">{agent.agentId}</CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      <MetricCell metric={agent.tasksCompleted} />
                      <MetricCell metric={agent.actionsExecuted} />
                      <MetricCell metric={agent.agentCostUsd} />
                      <MetricCell metric={agent.estimatedHoursSaved} />
                      <MetricCell metric={agent.estimatedLaborValueUsd} />
                      <MetricCell metric={agent.revenueInfluencedUsd} />
                      <MetricCell metric={agent.roiMultiple} />
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
