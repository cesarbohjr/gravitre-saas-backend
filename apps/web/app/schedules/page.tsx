"use client"

import { useCallback, useMemo, useState } from "react"
import useSWR from "swr"

import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader, LiveStatus } from "@/components/gravitre/nodus-product"
import { PhaseBand } from "@/components/gravitre/operating/operating-primitives"
import { Button } from "@/components/ui/button"
import { PAGE_FRAME, RADIUS } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { RefreshCw, CalendarClock, Plus } from "lucide-react"
import { useSchedules } from "@/lib/use-schedules"
import { workflowsApi } from "@/lib/api"
import type { ScheduleKind, ScheduleStatus } from "@/lib/schedules"
import { ScheduleEditorDialog } from "@/components/schedules/schedule-editor-dialog"
import { SchedulesView } from "./_components/schedules-view"
import { monthWindow } from "./_components/shared"

const ALL_KINDS_COUNT = 3

type SchedulePhase = "running" | "upcoming" | "failed" | "disabled" | "completed"

function schedulePhaseOf(status: ScheduleStatus): SchedulePhase {
  if (status === "running") return "running"
  if (status === "failed") return "failed"
  if (status === "disabled") return "disabled"
  if (status === "completed") return "completed"
  return "upcoming"
}

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

  const [phase, setPhase] = useState<SchedulePhase | null>(null)
  const phaseCounts = useMemo(() => {
    const counts: Record<SchedulePhase, number> = { running: 0, upcoming: 0, failed: 0, disabled: 0, completed: 0 }
    for (const item of items) counts[schedulePhaseOf(item.status)] += 1
    return counts
  }, [items])
  const visibleItems = useMemo(
    () => (phase ? items.filter((item) => schedulePhaseOf(item.status) === phase) : items),
    [items, phase],
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
      <div className={PAGE_FRAME} data-composition="operate">
        {/* Shared PageHeader rather than a bespoke title block, so the type
            scale, icon tile and action row match every other hub page. */}
        <GravitrePageHeader
          className="min-w-0"
          title="Schedules"
          description="All workflow schedules, task runs and training jobs across your organization."
          icon={<CalendarClock className="h-5 w-5" />}
          status={
            items.length > 0 ? (
              <LiveStatus tone={phaseCounts.running > 0 ? "live" : phaseCounts.failed > 0 ? "attention" : "idle"}>
                {phaseCounts.running > 0
                  ? `${phaseCounts.running} running now`
                  : phaseCounts.failed > 0
                    ? `${phaseCounts.failed} failed in this window`
                    : `${phaseCounts.upcoming} scheduled in this window`}
              </LiveStatus>
            ) : undefined
          }
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
          <>
          <PhaseBand
            label="Schedule phases in this window"
            className="-mx-[var(--np-page-pad-sm)] sm:-mx-[var(--np-page-pad)]"
            loading={isLoading && items.length === 0}
            phases={[
              { id: "running", label: "Running now", count: phaseCounts.running, tone: "live" },
              { id: "upcoming", label: "Scheduled", count: phaseCounts.upcoming, tone: "neutral" },
              { id: "failed", label: "Failed", count: phaseCounts.failed, tone: "risk" },
              { id: "disabled", label: "Disabled", count: phaseCounts.disabled, tone: "attention" },
              { id: "completed", label: "Completed", count: phaseCounts.completed, tone: "done" },
            ]}
            active={phase}
            onSelect={(next) => setPhase(next as SchedulePhase | null)}
          />
          <SchedulesView
            items={visibleItems}
            loading={isLoading}
            onRangeChange={handleRangeChange}
            onActiveKindsChange={handleKindsChange}
            workflowOptions={workflowOptions}
            workflowId={workflowId}
            onWorkflowChange={setWorkflowId}
            onRefresh={refresh}
          />
          </>
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
