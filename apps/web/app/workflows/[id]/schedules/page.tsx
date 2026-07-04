"use client"

import { useCallback, useMemo, useState, use } from "react"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { ArrowLeft, Plus, AlertCircle, RefreshCw, CheckCircle, Info } from "lucide-react"
import { workflowsApi } from "@/lib/api"
import { describeCron, type ScheduleKind } from "@/lib/schedules"
import { useSchedules } from "@/lib/use-schedules"
import { SchedulesView } from "@/app/schedules/_components/schedules-view"
import { monthWindow } from "@/app/schedules/_components/shared"

const cronExamples = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily at midnight", value: "0 0 * * *" },
  { label: "Weekdays at 9am", value: "0 9 * * 1-5" },
  { label: "Monthly", value: "0 0 1 * *" },
]

export default function WorkflowSchedulesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const isAdmin = true

  const [range, setRange] = useState(() => monthWindow(new Date()))
  const [kinds, setKinds] = useState<ScheduleKind[] | undefined>(undefined)

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

  const [newCron, setNewCron] = useState("")
  const [newEnabled, setNewEnabled] = useState<"enabled" | "disabled">("enabled")
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createSuccess, setCreateSuccess] = useState<string | null>(null)

  const cronPreview = useMemo(() => (newCron.trim() ? describeCron(newCron.trim()) : ""), [newCron])

  const handleCreateSchedule = async () => {
    if (!newCron.trim()) {
      setCreateError("Cron expression is required")
      return
    }
    setIsCreating(true)
    setCreateError(null)
    setCreateSuccess(null)
    try {
      await workflowsApi.createSchedule(id, {
        cron_expression: newCron.trim(),
        enabled: newEnabled === "enabled",
      })
      setNewCron("")
      setCreateSuccess("Schedule created successfully")
      refresh()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create schedule")
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <AppShell title="Schedules">
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        {/* Header */}
        <div className="mb-5">
          <Link
            href={`/workflows/${id}`}
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Workflow
          </Link>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-foreground">Schedules</h1>
              <span className="text-muted-foreground">·</span>
              <span className="font-mono text-sm text-muted-foreground">{id}</span>
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
        </div>

        {/* Create Schedule */}
        {isAdmin && (
          <div className="mb-5 rounded-xl border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Create schedule</h2>
            </div>
            <div className="space-y-4 p-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
                <div className="flex-1">
                  <label className="mb-1.5 block text-sm text-muted-foreground">
                    Cron expression
                  </label>
                  <Input
                    value={newCron}
                    onChange={(e) => setNewCron(e.target.value)}
                    placeholder="e.g., 0 */6 * * *"
                    className="h-9 font-mono"
                  />
                </div>
                <div className="w-full sm:w-32">
                  <label className="mb-1.5 block text-sm text-muted-foreground">Status</label>
                  <Select
                    value={newEnabled}
                    onValueChange={(v) => setNewEnabled(v as "enabled" | "disabled")}
                  >
                    <SelectTrigger className="h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="enabled">Enabled</SelectItem>
                      <SelectItem value="disabled">Disabled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  size="sm"
                  className="h-9 gap-2"
                  onClick={handleCreateSchedule}
                  disabled={isCreating}
                >
                  <Plus className="h-3.5 w-3.5" />
                  {isCreating ? "Creating..." : "Create"}
                </Button>
              </div>

              {/* Live human-readable preview */}
              {cronPreview && (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Info className="h-4 w-4 text-info" />
                  This runs: <span className="font-medium text-foreground">{cronPreview}</span>
                </p>
              )}

              {/* Example chips */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted-foreground">Examples:</span>
                {cronExamples.map((example) => (
                  <button
                    key={example.value}
                    type="button"
                    onClick={() => setNewCron(example.value)}
                    className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground"
                  >
                    {example.label} <span className="font-mono">({example.value})</span>
                  </button>
                ))}
              </div>

              {createError && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {createError}
                </div>
              )}
              {createSuccess && (
                <div className="flex items-center gap-2 text-sm text-success">
                  <CheckCircle className="h-4 w-4" />
                  {createSuccess}
                </div>
              )}
            </div>
          </div>
        )}

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
          />
        )}
      </div>
    </AppShell>
  )
}
