"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"

interface CostTabProps {
  isLoading: boolean
  cost?: Record<string, unknown>
}

export function CostTab({ isLoading, cost }: CostTabProps) {
  if (isLoading) {
    return <Skeleton className="h-64 w-full" />
  }

  const total = Number(cost?.totalCostUsd ?? 0)
  const byAgent = (cost?.byAgent ?? {}) as Record<string, { totalCostUsd?: number }>
  const byDepartment = (cost?.byDepartment ?? {}) as Record<string, { totalCostUsd?: number }>
  const byWorkflow = (cost?.byWorkflow ?? {}) as Record<string, { totalCostUsd?: number }>

  const agentEntries = Object.entries(byAgent)
    .sort(([, a], [, b]) => Number(b.totalCostUsd ?? 0) - Number(a.totalCostUsd ?? 0))
    .slice(0, 8)
  const maxAgentCost = Math.max(...agentEntries.map(([, r]) => Number(r.totalCostUsd ?? 0)), 1)

  if (total === 0 && agentEntries.length === 0) {
    return (
      <Empty className="border border-dashed">
        <EmptyHeader>
          <EmptyTitle>No cost data this month</EmptyTitle>
          <EmptyDescription>Usage attribution appears when agents consume billable resources.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className="space-y-6">
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader>
          <CardDescription>Month-to-date spend</CardDescription>
          <CardTitle className="text-3xl font-semibold tabular-nums">${total.toFixed(2)}</CardTitle>
        </CardHeader>
      </Card>

      {agentEntries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top agents</CardTitle>
            <CardDescription>Cost attribution by agent</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {agentEntries.map(([agentId, row]) => {
              const amount = Number(row.totalCostUsd ?? 0)
              const pct = (amount / maxAgentCost) * 100
              return (
                <div key={agentId} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="truncate text-muted-foreground">{agentId}</span>
                    <span className="font-medium tabular-nums">${amount.toFixed(2)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-secondary">
                    <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <BreakdownList title="By department" items={byDepartment} />
        <BreakdownList title="By workflow" items={byWorkflow} />
      </div>
    </div>
  )
}

function BreakdownList({
  title,
  items,
}: {
  title: string
  items: Record<string, { totalCostUsd?: number }>
}) {
  const entries = Object.entries(items).slice(0, 6)
  if (entries.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {entries.map(([id, row]) => (
          <div key={id} className="flex justify-between text-sm">
            <span className="truncate text-muted-foreground">{id}</span>
            <span className="tabular-nums">${Number(row.totalCostUsd ?? 0).toFixed(2)}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
