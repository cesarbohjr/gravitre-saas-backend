"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { RefreshCw, Info, CalendarClock } from "lucide-react"
import { useSchedules } from "@/lib/use-schedules"
import { SchedulesView } from "./_components/schedules-view"

export default function SchedulesPage() {
  const { items, isLoading, isSample, refresh } = useSchedules()

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

        {/* Sample data banner */}
        {isSample && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <span>
              No live schedules found for this organization yet — showing{" "}
              <span className="font-medium text-foreground">sample data</span> so you can preview
              the layout. Create a workflow schedule to see real items here.
            </span>
          </div>
        )}

        <SchedulesView items={items} />
      </div>
    </AppShell>
  )
}
