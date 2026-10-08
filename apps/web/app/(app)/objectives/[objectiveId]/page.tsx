"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { Target } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { TYPE } from "@/lib/design-system"
import { objectivesApi } from "@/lib/api"
import { businessEvidenceHref, describeBusinessValue, formatBusinessValue, humanizeMetricKey } from "@/lib/dashboard/business-kpis"

/** Progress on one objective, measured only on results re-read from the source system. */
export default function ObjectiveProgressPage() {
  const params = useParams<{ objectiveId: string }>()
  const id = params.objectiveId
  const { data, error, mutate } = useSWR(id ? `objective-progress:${id}` : null, () => objectivesApi.progress(id), {
    refreshInterval: 60_000,
  })
  const primary = data?.metrics.find((row) => row.metricKey === data.metricKey) ?? null
  const display = describeBusinessValue(primary, { loading: !data && !error, failed: Boolean(error) })

  return (
    <AppShell title="Objective">
      <div className="mx-auto max-w-5xl space-y-5 pb-8" data-composition="understand">
        <GravitrePageHeader eyebrow="Objective" title={data?.statement ?? "Objective"} icon={<Target className="h-5 w-5" />} />
        <div className="space-y-5 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]">
          {error ? (
            <WorkSectionErrorCard title="Could not load this objective" message={error instanceof Error ? error.message : "Unknown error"} onRetry={() => void mutate()} />
          ) : data ? (
            <>
              <section className="grid gap-4 border-y border-divide py-5 sm:grid-cols-3">
                <div>
                  <p className={TYPE.meta}>Verified so far this {data.period}</p>
                  <p className="text-3xl font-semibold tabular-nums">{display.value}</p>
                  <p className={TYPE.bodyMuted}>{display.hint}</p>
                </div>
                <div>
                  <p className={TYPE.meta}>Target</p>
                  <p className="text-3xl font-semibold tabular-nums">
                    {typeof data.target === "number" ? formatBusinessValue(data.target, primary?.unit) : "Not set"}
                  </p>
                  <p className={TYPE.bodyMuted}>A target, not a promise.</p>
                </div>
                <div>
                  <p className={TYPE.meta}>Remaining</p>
                  <p className="text-3xl font-semibold tabular-nums">
                    {typeof data.remaining === "number" ? formatBusinessValue(data.remaining, primary?.unit) : "Unknown"}
                  </p>
                  <p className={TYPE.bodyMuted}>{data.actionsAwaitingVerification} actions waiting for the source system to confirm.</p>
                </div>
              </section>
              <section>
                <h2 className={TYPE.sectionTitle}>Supporting results</h2>
                <ul className="mt-3 divide-y divide-divide">
                  {data.metrics.filter((row) => row.metricKey !== data.metricKey).map((row) => {
                    const value = describeBusinessValue(row)
                    return (
                      <li key={row.metricKey} className="flex items-center justify-between py-3">
                        <Link href={businessEvidenceHref(row.metricKey)} className="font-medium hover:underline">{humanizeMetricKey(row.metricKey)}</Link>
                        <span className="tabular-nums">{value.value}</span>
                      </li>
                    )
                  })}
                </ul>
              </section>
              <section>
                <h2 className={TYPE.sectionTitle}>Plan</h2>
                <ul className="mt-3 divide-y divide-divide">
                  {data.plan.map((step) => (
                    <li key={step.playKey} className="py-3">
                      <p className="font-medium">{step.name}</p>
                      <p className={TYPE.bodyMuted}>{step.why}</p>
                    </li>
                  ))}
                </ul>
                {data.planHistory.length > 1 ? (
                  <p className={TYPE.meta}>The plan has been revised {data.planHistory.length - 1} times as results and provider limits changed.</p>
                ) : null}
              </section>
            </>
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
