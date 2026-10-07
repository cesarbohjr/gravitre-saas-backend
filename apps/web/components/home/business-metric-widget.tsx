"use client"

import useSWR from "swr"
import { GravitreMetric } from "@/components/gravitre/nodus-product/metric"
import { businessMetricsApi } from "@/lib/api"
import {
  businessEvidenceHref,
  describeBusinessValue,
  toApiRange,
} from "@/lib/dashboard/business-kpis"
import type { DashboardRange } from "@/lib/dashboard/types"

/**
 * One business KPI, read from verified Play results (GET /api/metrics/business).
 * Missing evidence renders as "Not yet verified" or "Unknown", never as 0.
 */
export function BusinessMetricWidget({
  metricKey,
  title,
  range = "30d",
}: {
  metricKey: string
  title: string
  range?: DashboardRange
}) {
  const apiRange = toApiRange(range)
  const { data, error, isLoading } = useSWR(
    `business-metric:${metricKey}:${apiRange}`,
    () => businessMetricsApi.values(apiRange, [metricKey]),
  )
  const metric = data?.metrics.find((row) => row.metricKey === metricKey) ?? null
  const display = describeBusinessValue(metric, { loading: isLoading, failed: Boolean(error) })
  return (
    <div className="h-full" data-business-metric={metricKey} data-business-state={display.state}>
      <GravitreMetric
        label={title}
        value={display.value}
        hint={display.hint}
        href={businessEvidenceHref(metricKey, apiRange)}
        warning={display.state === "unknown" && Boolean(error)}
        className="h-full"
      />
    </div>
  )
}
