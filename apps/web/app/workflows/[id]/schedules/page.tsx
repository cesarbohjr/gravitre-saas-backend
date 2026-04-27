"use client"

import { useState, use } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiFetch, fetcher } from "@/lib/fetcher"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ArrowLeft, Plus, AlertCircle, RefreshCw, CheckCircle, Clock, Trash2 } from "lucide-react"

interface Schedule {
  id: string
  cron: string
  nextRun: string
  lastRun?: string
  status: "enabled" | "disabled"
}

const fallbackSchedules: Schedule[] = [
  {
    id: "sch-001",
    cron: "0 */6 * * *",
    nextRun: "2024-01-15 18:00 UTC",
    lastRun: "2024-01-15 12:00 UTC",
    status: "enabled",
  },
  {
    id: "sch-002",
    cron: "0 9 * * 1-5",
    nextRun: "2024-01-16 09:00 UTC",
    lastRun: "2024-01-15 09:00 UTC",
    status: "enabled",
  },
  {
    id: "sch-003",
    cron: "0 0 1 * *",
    nextRun: "2024-02-01 00:00 UTC",
    status: "disabled",
  },
]

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

  // Fetch schedules from API
  const { data, error, isLoading, mutate } = useSWR<{ schedules: Schedule[] }>(
    `/api/workflows/${id}/schedules`,
    fetcher,
    {
      fallbackData: { schedules: fallbackSchedules },
      revalidateOnFocus: false,
    }
  )

  const scheduleList = data?.schedules ?? fallbackSchedules

  // Create schedule form
  const [newCron, setNewCron] = useState("")
  const [newEnabled, setNewEnabled] = useState<"enabled" | "disabled">("enabled")
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createSuccess, setCreateSuccess] = useState<string | null>(null)

  const handleCreateSchedule = async () => {
    if (!newCron.trim()) {
      setCreateError("Cron expression is required")
      return
    }

    setIsCreating(true)
    setCreateError(null)
    setCreateSuccess(null)

    try {
      const response = await apiFetch(`/api/workflows/${id}/schedules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cronExpression: newCron,
          isEnabled: newEnabled === "enabled",
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || "Failed to create schedule")
      }

      setNewCron("")
      setCreateSuccess("Schedule created successfully")
      mutate()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create schedule")
    } finally {
      setIsCreating(false)
    }
  }

  const handleToggleStatus = async (scheduleId: string, currentStatus: "enabled" | "disabled") => {
    try {
      await apiFetch(`/api/workflows/${id}/schedules/${scheduleId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          isEnabled: currentStatus === "disabled",
        }),
      })
      mutate()
    } catch {
      // Handle error silently, rely on SWR retry
    }
  }

  const handleDeleteSchedule = async (scheduleId: string) => {
    if (!confirm("Are you sure you want to delete this schedule?")) return

    try {
      await apiFetch(`/api/workflows/${id}/schedules/${scheduleId}`, {
        method: "DELETE",
      })
      mutate()
    } catch {
      // Handle error silently
    }
  }

  return (
    <AppShell title="Schedules">
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <Link
            href={`/workflows/${id}`}
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Workflow
          </Link>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-foreground">Schedules</h1>
              <span className="text-muted-foreground">·</span>
              <span className="text-sm text-muted-foreground font-mono">{id}</span>
              <EnvironmentBadge environment="production" />
            </div>
            <Button variant="outline" size="sm" className="h-8 gap-2" onClick={() => mutate()}>
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* API Error Banner */}
        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            Failed to load schedules. Showing cached data.
          </div>
        )}

        {/* Create Schedule Card */}
        {isAdmin && (
          <div className="mb-6 rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Create Schedule</h2>
            </div>
            <div className="p-4 space-y-4">
              <div className="flex items-end gap-4">
                <div className="flex-1">
                  <label className="mb-1.5 block text-sm text-muted-foreground">
                    Cron Expression
                  </label>
                  <Input
                    value={newCron}
                    onChange={(e) => setNewCron(e.target.value)}
                    placeholder="e.g., 0 */6 * * *"
                    className="h-9 font-mono"
                  />
                </div>
                <div className="w-32">
                  <label className="mb-1.5 block text-sm text-muted-foreground">
                    Status
                  </label>
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

              {/* Helper text */}
              <div className="flex flex-wrap gap-2">
                <span className="text-xs text-muted-foreground">Examples:</span>
                {cronExamples.map((example) => (
                  <button
                    key={example.value}
                    type="button"
                    onClick={() => setNewCron(example.value)}
                    className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted/80 hover:text-foreground transition-colors"
                  >
                    {example.label} <span className="font-mono">({example.value})</span>
                  </button>
                ))}
              </div>

              {/* Messages */}
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

        {/* Schedules Table */}
        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Schedules</h2>
            <span className="text-xs text-muted-foreground">{scheduleList.length} schedule{scheduleList.length !== 1 ? "s" : ""}</span>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Cron
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Next Run
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Last Run
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Status
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                // Loading skeleton
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4 py-4">
                      <div className="h-4 w-24 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-4 w-32 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-4 w-32 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-5 w-16 animate-pulse rounded bg-muted" />
                    </td>
                    <td className="px-4 py-4">
                      <div className="h-7 w-24 animate-pulse rounded bg-muted ml-auto" />
                    </td>
                  </tr>
                ))
              ) : scheduleList.length === 0 ? (
                // Empty state
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center">
                    <Clock className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
                    <p className="text-sm text-muted-foreground">No schedules created yet.</p>
                  </td>
                </tr>
              ) : (
                // Data rows
                scheduleList.map((schedule) => (
                  <tr key={schedule.id}>
                    <td className="px-4 py-4">
                      <span className="font-mono text-sm text-foreground">{schedule.cron}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className="text-sm text-muted-foreground">{schedule.nextRun}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className="text-sm text-muted-foreground">{schedule.lastRun ?? "-"}</span>
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge
                        variant={schedule.status === "enabled" ? "success" : "muted"}
                        dot
                      >
                        {schedule.status}
                      </StatusBadge>
                    </td>
                    <td className="px-4 py-4 text-right">
                      {isAdmin && (
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => handleToggleStatus(schedule.id, schedule.status)}
                          >
                            {schedule.status === "enabled" ? "Disable" : "Enable"}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-destructive hover:text-destructive"
                            onClick={() => handleDeleteSchedule(schedule.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  )
}
