"use client"

import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
import { EmptyState } from "@/components/gravitre/empty-state"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useSchedules } from "@/lib/use-schedules"
import type { ScheduledItem, ScheduledItemKind } from "@/types/api"
import { Calendar, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

const kindLabels: Record<ScheduledItemKind, string> = {
  workflow: "Workflow",
  task: "Task run",
  job: "Training job",
}

const statusStyles: Record<string, string> = {
  enabled: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  disabled: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  running: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  queued: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  scheduled: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  completed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
}

function formatWhen(item: ScheduledItem): string {
  const raw = item.nextRunAt || item.startedAt || item.lastRunAt || item.completedAt
  if (!raw) return "—"
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

function ScheduleRow({ item }: { item: ScheduledItem }) {
  const statusClass = statusStyles[item.status] ?? statusStyles.scheduled
  const detailHref =
    item.kind === "workflow" && item.workflowId
      ? `/workflows/${item.workflowId}/schedules`
      : item.kind === "task"
        ? `/runs/${item.id}`
        : item.kind === "job"
          ? `/training`
          : undefined

  const content = (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-border/60 bg-card/40 p-4 transition-colors hover:border-violet-500/30 hover:bg-card/70">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium text-foreground line-clamp-1">{item.title}</p>
          <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
            {kindLabels[item.kind]}
          </Badge>
        </div>
        {item.subtitle ? (
          <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{item.subtitle}</p>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>{formatWhen(item)}</span>
          {item.cron ? <span className="font-mono">{item.cron}</span> : null}
          {typeof item.progress === "number" ? <span>{item.progress}%</span> : null}
          {item.occurrences?.length ? (
            <span>{item.occurrences.length} projected runs</span>
          ) : null}
        </div>
      </div>
      <Badge variant="outline" className={cn("shrink-0 capitalize", statusClass)}>
        {item.status.replace(/_/g, " ")}
      </Badge>
    </div>
  )

  if (detailHref) {
    return (
      <Link href={detailHref} className="block">
        {content}
      </Link>
    )
  }

  return content
}

export default function SchedulesPage() {
  const { items, isLoading, error, refresh } = useSchedules()

  return (
    <AppShell title="Schedules">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <PageHeader
          title="Schedules"
          description="Unified view of workflow cron schedules, task runs, and training jobs."
          icon={Calendar}
          actions={
            <Button variant="outline" size="sm" onClick={() => refresh()} disabled={isLoading}>
              <RefreshCw className={cn("mr-2 h-4 w-4", isLoading && "animate-spin")} />
              Refresh
            </Button>
          }
        />

        <p className="rounded-lg border border-dashed border-violet-500/30 bg-violet-500/5 px-4 py-3 text-sm text-muted-foreground">
          v0 stub — replace this list with calendar, filters, and timeline views. Data comes from{" "}
          <code className="text-xs">useSchedules()</code> → <code className="text-xs">GET /api/schedules</code>.
        </p>

        {error ? (
          <WorkSectionErrorCard
            title="Could not load schedules"
            message={error instanceof Error ? error.message : "Unknown error"}
            onRetry={() => refresh()}
          />
        ) : null}

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="No scheduled items yet"
            description="Create workflow schedules, run automations, or start a training job to see them here."
            action={{
              label: "Open automations",
              onClick: () => {
                window.location.href = "/workflows"
              },
              variant: "outline",
            }}
          />
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <ScheduleRow key={`${item.kind}-${item.id}`} item={item} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
