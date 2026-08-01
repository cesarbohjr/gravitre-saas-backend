"use client"

import { useCallback, useMemo, useState } from "react"
import useSWR from "swr"

import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
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
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        {/* Header */}
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <CalendarClock className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-xl font-semibold text-foreground">Schedules</h1>
              <p className="text-sm text-pretty text-muted-foreground">
                All workflow schedules, task runs and training jobs across your organization.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" className="h-8 gap-2" onClick={() => setCreateOpen(true)}>
              <Plus className="h-3.5 w-3.5" />
              New schedule
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-2"
              onClick={refresh}
              disabled={isLoading}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

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
