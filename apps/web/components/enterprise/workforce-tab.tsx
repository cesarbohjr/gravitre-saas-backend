"use client"

<<<<<<< HEAD
import useSWR from "swr"
import {
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowLeftRight,
  Wrench,
  Clock,
  AlertTriangle,
  Users,
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseWorkforceAnalytics } from "@/types/api"
import { KpiSkeleton } from "./enterprise-skeletons"

type Tone = "success" | "danger" | "info" | "warning" | "default"

const toneClasses: Record<Tone, { icon: string; value: string }> = {
  success: { icon: "text-success", value: "text-foreground" },
  danger: { icon: "text-destructive", value: "text-foreground" },
  info: { icon: "text-primary", value: "text-foreground" },
  warning: { icon: "text-amber-500", value: "text-foreground" },
  default: { icon: "text-muted-foreground", value: "text-foreground" },
}

function Sparkline({ tone }: { tone: Tone }) {
  // Decorative placeholder trend — backend does not return series yet.
  const points = [8, 12, 9, 16, 13, 20, 18, 24]
  const max = Math.max(...points)
  const stroke =
    tone === "success"
      ? "var(--success)"
      : tone === "danger"
        ? "var(--destructive)"
        : tone === "warning"
          ? "#f59e0b"
          : "var(--primary)"
  const w = 100
  const h = 32
  const step = w / (points.length - 1)
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${(i * step).toFixed(1)} ${(h - (p / max) * h).toFixed(1)}`)
    .join(" ")
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-8 w-full" preserveAspectRatio="none" aria-hidden>
      <path d={d} fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round" opacity={0.7} />
    </svg>
  )
}

function KpiCard({
  label,
  value,
  icon: Icon,
  tone = "default",
  suffix,
}: {
  label: string
  value: number
  icon: typeof CheckCircle2
  tone?: Tone
  suffix?: string
}) {
  const t = toneClasses[tone]
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
          <Icon className={cn("h-4 w-4", t.icon)} />
        </div>
        <div className={cn("text-2xl font-semibold tabular-nums", t.value)}>
          {value.toLocaleString()}
          {suffix ? <span className="text-base text-muted-foreground">{suffix}</span> : null}
        </div>
        <Sparkline tone={tone} />
      </CardContent>
    </Card>
  )
}

export function WorkforceTab() {
  const { data, isLoading } = useSWR<EnterpriseWorkforceAnalytics>(
    "enterprise-workforce",
    () => enterpriseApi.getWorkforceAnalytics(),
    { revalidateOnFocus: false },
  )

  if (isLoading) return <KpiSkeleton />

  const m = data
  const allZero =
    m &&
    m.tasksCompleted === 0 &&
    m.tasksFailed === 0 &&
    m.tasksRunning === 0 &&
    m.handoffs === 0 &&
    m.approvalWaitEvents === 0 &&
    m.slaBreaches === 0

  if (!m || allZero) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
            <Users className="h-6 w-6 text-muted-foreground" />
          </span>
          <div>
            <p className="text-sm font-medium text-foreground">No workforce activity yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Metrics will appear here once your agents start completing tasks.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <KpiCard label="Tasks completed" value={m.tasksCompleted} icon={CheckCircle2} tone="success" />
        <KpiCard label="Tasks failed" value={m.tasksFailed} icon={XCircle} tone="danger" />
        <KpiCard label="Tasks running" value={m.tasksRunning} icon={Loader2} tone="info" />
        <KpiCard label="Agent handoffs" value={m.handoffs} icon={ArrowLeftRight} tone="default" />
        <KpiCard
          label="Tool success rate"
          value={Math.round((m.toolSuccessRate ?? 0) * 100)}
          icon={Wrench}
          tone="success"
          suffix="%"
        />
        <KpiCard label="Approval waits" value={m.approvalWaitEvents} icon={Clock} tone="warning" />
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <CardTitle className="text-base">SLA breaches</CardTitle>
          </div>
          <CardDescription>
            Tasks that exceeded their service-level agreement window in the current period.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-baseline gap-2">
            <span
              className={cn(
                "text-3xl font-semibold tabular-nums",
                m.slaBreaches > 0 ? "text-destructive" : "text-success",
              )}
            >
              {m.slaBreaches}
            </span>
            <span className="text-sm text-muted-foreground">
              {m.slaBreaches === 0 ? "All tasks within SLA" : "breaches this period"}
            </span>
          </div>
=======
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
>>>>>>> eac2b609fbbcbbd202990b3258ff11c9e2f0003c
        </CardContent>
      </Card>
    </div>
  )
}
