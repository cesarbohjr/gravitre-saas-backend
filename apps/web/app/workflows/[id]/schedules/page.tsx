"use client"

import { useCallback, useState, use } from "react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { ArrowLeft, Plus, RefreshCw } from "lucide-react"
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
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <div className="mb-5">
          <Link
            href={`/workflows/${id}`}
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Workflow
          </Link>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-semibold text-foreground">Schedules</h1>
                <span className="text-muted-foreground">·</span>
                <span className="font-mono text-sm text-muted-foreground">{id.slice(0, 8)}…</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Create one-time or recurring runs for this workflow.{" "}
                {items.find((i) => i.cron)?.cron
                  ? `Example: ${describeCron(items.find((i) => i.cron)!.cron!)}`
                  : "Use New schedule to get started."}
              </p>
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
