"use client"

import { useState } from "react"
import useSWR from "swr"
import { TrendingUp } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { OutcomeMethodologyCallout } from "@/components/outcome/outcome-methodology-callout"
import { MetricProvenanceBadge } from "@/components/outcome/metric-provenance-badge"
import {
  OPERATIONAL_SUCCESS_RATE_LABEL,
  OPERATIONAL_TASKS_COMPLETED_LABEL,
} from "@/lib/outcome-labels"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"
import { HubTabs } from "@/components/gravitre/hub-tabs"
import { StatsGrid, StatCard } from "@/components/gravitre/page-header"

type RangeId = "7d" | "30d" | "90d"

const RANGE_TABS: { id: RangeId; label: string }[] = [
  { id: "7d", label: "7d" },
  { id: "30d", label: "30d" },
  { id: "90d", label: "90d" },
]

export default function LiteResultsPage() {
  const { user, loading } = useAuth()
  const [range, setRange] = useState<RangeId>("30d")
  const { data, isLoading } = useSWR(
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
      <OutcomeMethodologyCallout variant="operational" />

      <StatsGrid columns={4}>
        <StatCard
          label={OPERATIONAL_TASKS_COMPLETED_LABEL}
          value={summary?.tasks_completed ?? 0}
        />
        <StatCard
          label={OPERATIONAL_SUCCESS_RATE_LABEL}
          value={`${summary?.success_rate ?? 0}%`}
          variant="success"
        />
        <StatCard
          label="Avg completion (hrs)"
          value={summary?.avg_completion_time_hours ?? 0}
          variant="info"
        />
        <StatCard
          label="Workflows used"
          value={summary?.by_workflow.length ?? 0}
        />
      </StatsGrid>

      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Results by Workflow
        </h2>
        <MetricProvenanceBadge kind="operational" />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {(summary?.by_workflow ?? []).map((item) => (
          <Card key={item.workflow_name} className="border-border/50 p-4">
            <div className="flex items-center justify-between">
              <p className="font-medium">{item.workflow_name}</p>
              <Badge variant="outline">{item.count}</Badge>
            </div>
          </Card>
        ))}
        {!summary?.by_workflow?.length ? (
          <Card className="p-6 text-sm text-muted-foreground md:col-span-2">
            No workflow results in this range.
          </Card>
        ) : null}
      </div>

      <div>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Recent Tasks
        </h2>
        <div className="space-y-2">
          {(data?.recent ?? []).map((task) => (
            <Card key={task.id} className="border-border/50 p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{task.workflow_name}</p>
                <Badge variant="outline">{task.status}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {task.input_summary || "No summary"}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </LitePageShell>
  )
}
