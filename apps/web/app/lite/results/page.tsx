"use client"

import { useState } from "react"
import useSWR from "swr"
import { TrendingUp } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { OutcomeMethodologyCallout } from "@/components/outcome/outcome-methodology-callout"
import { MetricProvenanceBadge } from "@/components/outcome/metric-provenance-badge"
import {
  OPERATIONAL_SUCCESS_RATE_LABEL,
  OPERATIONAL_TASKS_COMPLETED_LABEL,
} from "@/lib/outcome-labels"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"
import { HubTabs } from "@/components/gravitre/hub-tabs"
import { GravitreMetric } from "@/components/gravitre/nodus-product"

type RangeId = "7d" | "30d" | "90d"

const RANGE_TABS: { id: RangeId; label: string }[] = [
  { id: "7d", label: "7d" },
  { id: "30d", label: "30d" },
  { id: "90d", label: "90d" },
]

export default function LiteResultsPage() {
  const { user, loading } = useAuth()
  const [range, setRange] = useState<RangeId>("30d")
  const { data, isLoading, error, mutate } = useSWR(
    user ? ["lite-results", user.id, range] : null,
    () => liteApi.getResults(range),
    { revalidateOnFocus: false, refreshInterval: 20000 },
  )

  if (!loading && !isLoading && !user) {
    return (
      <LitePageShell title="Results" description="Sign in to continue." icon={TrendingUp}>
        <p className="text-sm text-muted-foreground">Sign in required.</p>
      </LitePageShell>
    )
  }

  const summary = data?.summary

  return (
    <LitePageShell
      title="Results"
      description="Track your AI team's performance."
      icon={TrendingUp}
      loading={loading || isLoading}
      loadingLabel="Loading results"
      headerChildren={
        <HubTabs
          tabs={RANGE_TABS}
          active={range}
          onSelect={setRange}
          ariaLabel="Results time range"
          size="sm"
        />
      }
    >
      {error ? <WorkSectionErrorCard title="Could not load results" message={error instanceof Error ? error.message : "Try again to retrieve the latest data."} onRetry={() => void mutate()} /> : null}
      <OutcomeMethodologyCallout variant="operational" />

      <section className="mb-4 grid grid-cols-1 gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-4">
        <GravitreMetric
          label={OPERATIONAL_TASKS_COMPLETED_LABEL}
          value={summary?.tasks_completed ?? "Not reported"}
        />
        <GravitreMetric
          label={OPERATIONAL_SUCCESS_RATE_LABEL}
          value={summary?.success_rate == null ? "Not reported" : `${summary.success_rate}%`}
        />
        <GravitreMetric
          label="Avg completion (hrs)"
          value={summary?.avg_completion_time_hours ?? "Not reported"}
        />
        <GravitreMetric
          label="Workflows used"
          value={summary?.by_workflow?.length ?? "Not reported"}
        />
      </section>

      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-muted-foreground">
          Results by workflow
        </h2>
        <MetricProvenanceBadge kind="operational" />
      </div>
      <div className="mb-6 divide-y divide-divide border-y border-divide">
        {(summary?.by_workflow ?? []).map((item) => (
          <div key={item.workflow_name} className="py-3">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
              <p className="min-w-0 break-words font-medium">{item.workflow_name}</p>
              <Badge variant="outline">{item.count}</Badge>
            </div>
          </div>
        ))}
        {!error && !summary?.by_workflow?.length ? (
          <div className="p-6 text-sm text-muted-foreground md:col-span-2">
            {summary?.by_workflow == null ? "Workflow results not reported." : "No workflow results in this range."}
          </div>
        ) : null}
      </div>

      <div>
        <h2 className="mb-4 text-sm font-semibold text-muted-foreground">
          Recent tasks
        </h2>
        <div className="divide-y divide-divide border-y border-divide">
          {(data?.recent ?? []).map((task) => (
            <div key={task.id} className="py-3">
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 break-words text-sm font-medium">{task.workflow_name}</p>
                <Badge variant="outline">{task.status}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {task.input_summary || "No summary"}
              </p>
            </div>
          ))}
        </div>
      </div>
    </LitePageShell>
  )
}
