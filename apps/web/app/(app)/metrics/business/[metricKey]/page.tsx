"use client"

import Link from "next/link"
import { useParams, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { ArrowLeft, BadgeCheck } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { TYPE } from "@/lib/design-system"
import { businessMetricsApi, type BusinessMetricRange } from "@/lib/api"
import { describeBusinessValue, formatBusinessValue, humanizeMetricKey } from "@/lib/dashboard/business-kpis"

const RANGES: BusinessMetricRange[] = ["7d", "30d", "90d", "365d"]

function sourceLabel(record: { system?: string; record_type?: string; record_id?: string }): string {
  return [record.system, record.record_type, record.record_id].filter(Boolean).join(" · ")
}

/** Every verified result behind one business KPI, with the source record each was re-read from. */
export default function BusinessMetricEvidencePage() {
  const params = useParams<{ metricKey: string }>()
  const search = useSearchParams()
  const metricKey = decodeURIComponent(params.metricKey ?? "")
  const requested = search?.get("range") as BusinessMetricRange | null
  const range: BusinessMetricRange = requested && RANGES.includes(requested) ? requested : "30d"
  const { data: catalog } = useSWR("business-metric-catalog", () => businessMetricsApi.catalog())
  const { data, error, isLoading, mutate } = useSWR(
    metricKey ? `business-metric-evidence:${metricKey}:${range}` : null,
    () => businessMetricsApi.evidence(metricKey, range),
  )
  const definition = catalog?.metrics.find((row) => row.metricKey === metricKey)
  const title = definition?.label ?? humanizeMetricKey(metricKey)
  const display = describeBusinessValue(data ?? null, { loading: isLoading, failed: Boolean(error) })

  return (
    <AppShell title={title}>
      <div className="mx-auto max-w-5xl space-y-5 pb-8" data-composition="understand">
        <GravitrePageHeader
          eyebrow="Business metric"
          title={title}
          description={definition?.description}
          icon={<BadgeCheck className="h-5 w-5" />}
          actions={
            <Button variant="ghost" size="sm" className="min-h-11" asChild>
              <Link href="/"><ArrowLeft className="size-4" />Back to dashboard</Link>
            </Button>
          }
        />
        <div className="space-y-5 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]">
          <nav className="flex gap-2" aria-label="Range">
            {RANGES.map((value) => (
              <Button key={value} variant={value === range ? "default" : "outline"} size="sm" asChild>
                <Link href={`/metrics/business/${encodeURIComponent(metricKey)}?range=${value}`}>{value}</Link>
              </Button>
            ))}
          </nav>
          {error ? (
            <WorkSectionErrorCard
              title="Could not load this metric"
              message={error instanceof Error ? error.message : "Unknown error"}
              onRetry={() => void mutate()}
            />
          ) : (
            <>
              <section className="border-y border-divide py-5" data-business-state={display.state}>
                <p className={TYPE.meta}>Verified value</p>
                <div className="mt-1 text-3xl font-semibold tabular-nums">{isLoading ? <Skeleton className="h-9 w-32" /> : display.value}</div>
                <p className={TYPE.bodyMuted}>{display.hint}</p>
                {definition?.sourceSystem ? (
                  <p className={TYPE.bodyMuted}>Counted only after Gravitre re-reads the record in {definition.sourceSystem}.</p>
                ) : null}
              </section>

              <section>
                <h2 className={TYPE.sectionTitle}>Results that count</h2>
                {data && data.contributions.length === 0 ? (
                  <p className={TYPE.bodyMuted}>No result has been confirmed in the source system in this range.</p>
                ) : (
                  <ul className="mt-3 divide-y divide-divide">
                    {(data?.contributions ?? []).map((row) => (
                      <li key={row.outcomeId} className="flex flex-wrap items-center justify-between gap-3 py-3">
                        <div className="min-w-0">
                          <p className="font-medium">
                            {typeof row.value === "number" ? formatBusinessValue(row.value, row.unit, row.currency) : "Counted"}
                            {row.countedInTotal ? "" : " · assisted, not added to the total"}
                          </p>
                          <p className={TYPE.meta}>{row.sourceRecords.map(sourceLabel).join(", ") || "Source record"}</p>
                        </div>
                        {row.evidenceHref ? (
                          <Button variant="ghost" size="sm" asChild>
                            <Link href={row.evidenceHref}>See evidence</Link>
                          </Button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {data && data.exceptions.length > 0 ? (
                <section>
                  <h2 className={TYPE.sectionTitle}>Did not count</h2>
                  <ul className="mt-3 divide-y divide-divide">
                    {data.exceptions.map((row, index) => (
                      <li key={row.outcomeId ?? index} className="py-3">
                        <p className="font-medium">{row.kind === "verified_failure" ? "Confirmed not achieved" : "No decisive evidence"}</p>
                        <p className={TYPE.bodyMuted}>{row.message}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
