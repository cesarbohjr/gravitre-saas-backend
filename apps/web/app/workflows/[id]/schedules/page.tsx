"use client"

import { useCallback, useState, use } from "react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { GravitrePageHeader, LiveStatus } from "@/components/gravitre/nodus-product"
import { PAGE_FRAME, RADIUS } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { ArrowLeft, Plus, RefreshCw, CalendarClock } from "lucide-react"
import { describeCron, type ScheduleKind } from "@/lib/schedules"
import { useSchedules } from "@/lib/use-schedules"
import { ScheduleEditorDialog } from "@/components/schedules/schedule-editor-dialog"
import { SchedulesView } from "@/app/schedules/_components/schedules-view"
import { monthWindow } from "@/app/schedules/_components/shared"

export default function WorkflowSchedulesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)

  const [range, setRange] = useState(() => monthWindow(new Date()))
  const [kinds, setKinds] = useState<ScheduleKind[] | undefined>(undefined)
  const [createOpen, setCreateOpen] = useState(false)

  const { items, isLoading, error, refresh } = useSchedules({
    workflowId: id,
    from: range.from,
    to: range.to,
    kinds,
  })

  const handleRangeChange = useCallback((from: Date, to: Date) => {
    setRange({ from: from.toISOString(), to: to.toISOString() })
  }, [])

  const handleKindsChange = useCallback((next: ScheduleKind[]) => {
    setKinds(next.length >= 3 ? undefined : next)
  }, [])

  return (
    <AppShell title="Schedules">
      <div className={PAGE_FRAME} data-composition="operate">
        <Link
          href={`/workflows/${id}`}
          className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to workflow
        </Link>

        <GravitrePageHeader
          className="min-w-0"
          title="Workflow schedules"
          description={
            items.find((item) => item.cron)?.cron
              ? `Recurring and one-time execution windows · ${describeCron(items.find((item) => item.cron)!.cron!)}`
              : "Recurring and one-time execution windows for this workflow."
          }
          icon={<CalendarClock className="h-5 w-5" />}
          status={
            <LiveStatus tone={isLoading ? "idle" : items.length > 0 ? "live" : "idle"}>
              {isLoading ? "Syncing schedules" : items.length > 0 ? `${items.length} in this window` : "No schedules in window"}
            </LiveStatus>
          }
          actions={
            <>
              <Button
                size="sm"
                className={cn("shrink-0 gap-2", RADIUS.control)}
                onClick={() => setCreateOpen(true)}
              >
                <Plus className="h-3.5 w-3.5" />
                New schedule
              </Button>
              <Button
                variant="outline"
                size="sm"
                className={cn("shrink-0 gap-2", RADIUS.control)}
                onClick={refresh}
                disabled={isLoading}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
                Refresh
              </Button>
            </>
          }
        />

        {error && items.length === 0 ? (
          <WorkSectionErrorCard
            title="Couldn't load schedules"
            message="We couldn't reach the schedules service. Please try again."
            onRetry={refresh}
          />
        ) : (
          <SchedulesView
            items={items}
            loading={isLoading}
            onRangeChange={handleRangeChange}
            onActiveKindsChange={handleKindsChange}
            workflowOptions={[{ id, name: "This workflow" }]}
            onRefresh={refresh}
          />
        )}

        <ScheduleEditorDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          workflows={[{ id, name: "This workflow" }]}
          lockedWorkflowId={id}
          onSaved={() => refresh()}
        />
      </div>
    </AppShell>
  )
}
