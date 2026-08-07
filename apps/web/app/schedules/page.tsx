"use client"

import { useCallback, useMemo, useState } from "react"
import useSWR from "swr"

import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { RADIUS } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { RefreshCw, CalendarClock, Plus } from "lucide-react"
import { useSchedules } from "@/lib/use-schedules"
import { workflowsApi } from "@/lib/api"
import type { ScheduleKind } from "@/lib/schedules"
import { ScheduleEditorDialog } from "@/components/schedules/schedule-editor-dialog"
import { SchedulesView } from "./_components/schedules-view"
import { monthWindow } from "./_components/shared"

const ALL_KINDS_COUNT = 3

export default function SchedulesPage() {
  const [range, setRange] = useState(() => monthWindow(new Date()))
  const [kinds, setKinds] = useState<ScheduleKind[] | undefined>(undefined)
  const [workflowId, setWorkflowId] = useState<string | undefined>(undefined)
  const [createOpen, setCreateOpen] = useState(false)

  const { items, isLoading, error, refresh } = useSchedules({
    from: range.from,
    to: range.to,
    kinds,
    workflowId,
  })

  // Populate the workflow filter from the org's workflow list.
  const { data: workflowData } = useSWR(["schedules-workflows"], () => workflowsApi.list(), {
    revalidateOnFocus: false,
  })
  const workflowOptions = useMemo(
    () => (workflowData?.workflows ?? []).map((w) => ({ id: w.id, name: w.name })),
    [workflowData],
  )

  const handleRangeChange = useCallback((from: Date, to: Date) => {
    setRange({ from: from.toISOString(), to: to.toISOString() })
  }, [])

  const handleKindsChange = useCallback((next: ScheduleKind[]) => {
    // Treat "all selected" as no filter to keep the request lean.
    setKinds(next.length >= ALL_KINDS_COUNT ? undefined : next)
  }, [])

  return (
    <AppShell title="Schedules">
      <div className="mx-auto w-full min-w-0 max-w-7xl p-4 sm:p-6">
        {/* Shared PageHeader rather than a bespoke title block, so the type
            scale, icon tile and action row match every other hub page. */}
        <PageHeader
          className="mb-5 min-w-0 border-0 p-0"
          eyebrow="Operations"
          title="Schedules"
          description="All workflow schedules, task runs and training jobs across your organization."
          icon={CalendarClock}
          actions={
            <>
              <Button
                size="sm"
                className={cn("shrink-0 gap-2", RADIUS.control)}
                onClick={() => setCreateOpen(true)}
              >
                <Plus className="h-3.5 w-3.5" />
                <span className="whitespace-nowrap">New schedule</span>
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
            workflowOptions={workflowOptions}
            workflowId={workflowId}
            onWorkflowChange={setWorkflowId}
            onRefresh={refresh}
          />
        )}

        <ScheduleEditorDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          workflows={workflowOptions}
          lockedWorkflowId={workflowId}
          onSaved={() => refresh()}
        />
      </div>
    </AppShell>
  )
}
