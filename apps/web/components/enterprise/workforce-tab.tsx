"use client"

import { StatsGrid, StatCard } from "@/components/gravitre/page-header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"

interface WorkforceTabProps {
  isLoading: boolean
  analytics?: Record<string, unknown>
}

export function WorkforceTab({ isLoading, analytics }: WorkforceTabProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  const tasksCompleted = Number(analytics?.tasksCompleted ?? 0)
  const tasksFailed = Number(analytics?.tasksFailed ?? 0)
  const tasksRunning = Number(analytics?.tasksRunning ?? 0)
  const handoffs = Number(analytics?.handoffs ?? 0)
  const toolSuccessRate = Number(analytics?.toolSuccessRate ?? 0)
  const approvalWait = Number(analytics?.approvalWaitEvents ?? 0)
  const slaBreaches = Number(analytics?.slaBreaches ?? 0)

  const allZero =
    tasksCompleted + tasksFailed + tasksRunning + handoffs + approvalWait + slaBreaches === 0 &&
    toolSuccessRate === 0

  return (
    <div className="space-y-6">
      {allZero ? (
        <Empty className="border border-dashed">
          <EmptyHeader>
            <EmptyTitle>No workforce activity yet</EmptyTitle>
            <EmptyDescription>Metrics appear once agents complete tasks, handoffs, or approvals.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <>
          <StatsGrid columns={4}>
            <StatCard label="Completed" value={tasksCompleted} variant="success" />
            <StatCard label="Failed" value={tasksFailed} variant="danger" />
            <StatCard label="Running" value={tasksRunning} variant="info" />
            <StatCard label="Handoffs" value={handoffs} variant="default" />
          </StatsGrid>
          <StatsGrid columns={3}>
            <StatCard label="Tool success" value={`${toolSuccessRate}%`} variant="success" />
            <StatCard label="Approval waits" value={approvalWait} variant="warning" />
            <StatCard label="SLA breaches" value={slaBreaches} variant="danger" />
          </StatsGrid>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent activity</CardTitle>
          <CardDescription>Handoff and approval events (coming soon)</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Detailed event timeline will appear here in a future release.</p>
        </CardContent>
      </Card>
    </div>
  )
}
