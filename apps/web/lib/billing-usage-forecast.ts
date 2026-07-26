import type { BillingOverview } from "@/types/api"
import { planLimitsFor } from "@/lib/plan-limits"

export type UsageMetricRow = {
  name: string
  used: number
  limit: number
  unit?: string
}

export type ForecastPoint = {
  label: string
  actual: number | null
  projected: number | null
  safe: number
}

export function buildUsageMetricsFromOverview(overview: BillingOverview | undefined): UsageMetricRow[] {
  const usage = overview?.usage
  if (!usage) return []
  const tier = usage.tier ?? overview?.subscription?.tier ?? "node"
  const fallback = planLimitsFor(tier)
  return [
    {
      name: "Workflow Runs",
      used: usage.totals.workflow_runs ?? 0,
      limit: usage.workflow_runs_included ?? fallback.workflowRuns,
    },
    {
      name: "AI Credits",
      used: usage.totals.ai_tokens ?? 0,
      limit: usage.ai_credits_included ?? fallback.aiCredits,
    },
    {
      name: "API Calls",
      used: usage.totals.api_calls ?? 0,
      limit: Math.max(usage.totals.api_calls ?? 0, 500000),
    },
  ]
}

export function buildWeeklySeriesFromOverview(overview: BillingOverview | undefined): number[] {
  const weekly = overview?.usage?.weekly_totals
  if (Array.isArray(weekly) && weekly.length > 0) {
    return weekly.map((value) => Number(value) || 0)
  }
  const total = overview?.usage?.totals.workflow_runs ?? 0
  if (total <= 0) return [0]
  const weeks = 4
  const perWeek = Math.max(1, Math.round(total / weeks))
  return Array.from({ length: weeks }, (_, index) =>
    index === weeks - 1 ? total - perWeek * (weeks - 1) : perWeek,
  )
}

export function buildUsageForecast(params: {
  overview?: BillingOverview
  workflowLimit?: number
  periodEndLabel?: string
}): {
  weeklyData: Array<{ week: string; value: number }>
  workflowUsed: number
  workflowLimit: number
  projectedTotal: number
  projectedPct: number
  willExceed: boolean
  forecastSeries: ForecastPoint[]
  forecastStatus: { label: string; accent: string; soft: string; dot: string }
  weeksInPeriod: number
  researchOverageUsd: number
  totalEstimatedOverageUsd: number
} {
  const usage = params.overview?.usage
  const tier = usage?.tier ?? params.overview?.subscription?.tier ?? "node"
  const fallback = planLimitsFor(tier)
  const workflowLimit =
    params.workflowLimit ??
    usage?.workflow_runs_included ??
    fallback.workflowRuns
  const weeksInPeriod = 4.345
  const periodEndLabel =
    params.periodEndLabel ??
    (params.overview?.subscription?.current_period_end
      ? new Date(params.overview.subscription.current_period_end).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        })
      : "Period end")

  const series = buildWeeklySeriesFromOverview(params.overview)
  const weeklyData = series.map((value, index) => ({
    week: `Week ${index + 1}`,
    value,
  }))

  let acc = 0
  const workflowCumulative = weeklyData.map((w) => {
    acc += w.value
    return acc
  })
  const workflowUsed =
    usage?.totals.workflow_runs ??
    workflowCumulative[workflowCumulative.length - 1] ??
    0
  const weeksElapsed = Math.max(1, weeklyData.length)
  const recentRate =
    weeklyData.slice(-2).reduce((sum, w) => sum + w.value, 0) / Math.min(2, weeklyData.length)
  const projectedTotal = Math.round(
    workflowUsed + recentRate * Math.max(0, weeksInPeriod - weeksElapsed),
  )
  const projectedPct = workflowLimit > 0 ? Math.round((projectedTotal / workflowLimit) * 100) : 0
  const willExceed = projectedTotal > workflowLimit

  const safeBurnAt = (elapsedWeeks: number) =>
    Math.round(workflowLimit * (Math.min(elapsedWeeks, weeksInPeriod) / weeksInPeriod))

  const forecastSeries: ForecastPoint[] = workflowCumulative.map((v, i) => ({
    label: `W${i + 1}`,
    actual: v,
    projected: i === workflowCumulative.length - 1 ? v : null,
    safe: safeBurnAt(i + 1),
  }))
  forecastSeries.push({
    label: periodEndLabel,
    actual: null,
    projected: projectedTotal,
    safe: workflowLimit,
  })

  const forecastStatus = willExceed
    ? { label: "Will exceed limit", accent: "text-destructive", soft: "bg-destructive/10", dot: "bg-destructive" }
    : projectedPct >= 75
      ? { label: "Approaching limit", accent: "text-warning", soft: "bg-warning/10", dot: "bg-warning" }
      : { label: "On track", accent: "text-success", soft: "bg-success/10", dot: "bg-success" }

  const showResearch = Boolean(usage?.research_lookups_billing_visible)
  const researchOverageUsd = showResearch ? Number(usage?.overage_research_cost_usd ?? 0) : 0
  const outputOverageUsd = Number(usage?.overage_cost_usd ?? 0)
  const totalEstimatedOverageUsd = outputOverageUsd + researchOverageUsd

  return {
    weeklyData,
    workflowUsed,
    workflowLimit,
    projectedTotal,
    projectedPct,
    willExceed,
    forecastSeries,
    forecastStatus,
    weeksInPeriod,
    researchOverageUsd,
    totalEstimatedOverageUsd,
  }
}
