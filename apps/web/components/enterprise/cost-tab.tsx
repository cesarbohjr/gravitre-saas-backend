"use client"

import useSWR from "swr"
import { DollarSign, Bot, Building2, Workflow } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseCostAttribution } from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

function formatUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n || 0)
}

function toSortedEntries(record: Record<string, number> | undefined): [string, number][] {
  if (!record) return []
  return Object.entries(record).sort((a, b) => b[1] - a[1])
}

function BarBreakdown({ entries, total }: { entries: [string, number][]; total: number }) {
  const max = entries.length ? Math.max(...entries.map(([, v]) => v)) : 0
  if (!entries.length) {
    return <p className="py-4 text-sm text-muted-foreground">No cost data for this dimension yet.</p>
  }
  return (
    <div className="space-y-3">
      {entries.map(([label, value]) => {
        const pct = max > 0 ? (value / max) * 100 : 0
        const share = total > 0 ? (value / total) * 100 : 0
        return (
          <div key={label} className="space-y-1">
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate font-medium text-foreground">{label}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {formatUsd(value)}
                <span className="ml-1.5 text-xs text-muted-foreground/60">{share.toFixed(0)}%</span>
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function CompactList({
  entries,
  total,
  icon: Icon,
  title,
  description,
}: {
  entries: [string, number][]
  total: number
  icon: typeof Building2
  title: string
  description: string
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-primary" />
          <CardTitle className="text-base">{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {entries.length ? (
          <ul className="divide-y divide-border">
            {entries.map(([label, value]) => {
              const share = total > 0 ? (value / total) * 100 : 0
              return (
                <li key={label} className="flex items-center justify-between gap-2 py-2 first:pt-0 last:pb-0">
                  <span className="truncate text-sm text-foreground">{label}</span>
                  <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
                    {formatUsd(value)}
                    <span className="ml-1.5 text-xs text-muted-foreground/60">{share.toFixed(0)}%</span>
                  </span>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        )}
      </CardContent>
    </Card>
  )
}

export function CostTab() {
  const { data, isLoading } = useSWR<EnterpriseCostAttribution>(
    "enterprise-cost",
    () => enterpriseApi.getCostAttribution(),
    { revalidateOnFocus: false },
  )

  if (isLoading) return <TabSkeleton rows={4} />

  const total = data?.totalCostUsd ?? 0
  const byAgent = toSortedEntries(data?.byAgent).slice(0, 8)
  const byDepartment = toSortedEntries(data?.byDepartment)
  const byWorkflow = toSortedEntries(data?.byWorkflow)

  return (
    <div className="space-y-4">
      {/* Hero metric */}
      <Card>
        <CardContent className="flex flex-col gap-1 p-6">
          <div className="flex items-center gap-2 text-muted-foreground">
            <DollarSign className="h-4 w-4" />
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Month-to-date spend
            </span>
          </div>
          <span className="text-4xl font-semibold tabular-nums text-foreground">
            {formatUsd(total)}
          </span>
          <span className="text-sm text-muted-foreground">
            Attributed across {byAgent.length} agents, {byDepartment.length} departments,{" "}
            {byWorkflow.length} workflows
          </span>
        </CardContent>
      </Card>

      {/* Top agents */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Cost by agent</CardTitle>
          </div>
          <CardDescription>Top agents by spend in the current period.</CardDescription>
        </CardHeader>
        <CardContent>
          <BarBreakdown entries={byAgent} total={total} />
        </CardContent>
      </Card>

      {/* Department + workflow lists */}
      <div className={cn("grid gap-4", "md:grid-cols-2")}>
        <CompactList
          entries={byDepartment}
          total={total}
          icon={Building2}
          title="By department"
          description="Spend grouped by department."
        />
        <CompactList
          entries={byWorkflow}
          total={total}
          icon={Workflow}
          title="By workflow"
          description="Spend grouped by automation."
        />
      </div>
    </div>
  )
}
