"use client"

import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { CalendarClock, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { workflowsApi } from "@/lib/api"
import { describeCron } from "@/lib/schedules"
import { toDateTimeLocalValue } from "@/lib/schedules/actions"
import type { WorkflowSchedule, WorkflowScheduleType } from "@/types/api"

const RECURRENCE_PRESETS = [
  { id: "hourly", label: "Every hour", cron: "0 * * * *" },
  { id: "every-6h", label: "Every 6 hours", cron: "0 */6 * * *" },
  { id: "daily", label: "Daily at midnight (UTC cron)", cron: "0 0 * * *" },
  { id: "weekdays", label: "Weekdays at 9:00", cron: "0 9 * * 1-5" },
  { id: "weekly", label: "Weekly (Sunday midnight)", cron: "0 0 * * 0" },
  { id: "monthly", label: "Monthly (1st at midnight)", cron: "0 0 1 * *" },
  { id: "custom", label: "Custom cron", cron: "" },
] as const

const COMMON_TIMEZONES = [
  "UTC",
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "Europe/London",
  "Europe/Paris",
  "Asia/Tokyo",
  "Australia/Sydney",
]

function guessBrowserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
  } catch {
    return "UTC"
  }
}

function localValueToIso(value: string): string | null {
  if (!value.trim()) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toISOString()
}

export type ScheduleEditorWorkflowOption = { id: string; name: string }

export type ScheduleEditorInitial = {
  scheduleId?: string
  workflowId?: string
  name?: string
  scheduleType?: WorkflowScheduleType
  cron?: string
  timezone?: string
  runAt?: string
  endsAt?: string
  enabled?: boolean
}

export function ScheduleEditorDialog({
  open,
  onOpenChange,
  workflows,
  lockedWorkflowId,
  initial,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  workflows: ScheduleEditorWorkflowOption[]
  lockedWorkflowId?: string
  initial?: ScheduleEditorInitial | null
  onSaved?: (schedule: WorkflowSchedule) => void
}) {
  const isEdit = Boolean(initial?.scheduleId)
  const [workflowId, setWorkflowId] = useState("")
  const [name, setName] = useState("")
  const [scheduleType, setScheduleType] = useState<WorkflowScheduleType>("recurring")
  const [presetId, setPresetId] = useState<string>("daily")
  const [cron, setCron] = useState("0 0 * * *")
  const [timezone, setTimezone] = useState("UTC")
  const [runAtLocal, setRunAtLocal] = useState("")
  const [endsAtLocal, setEndsAtLocal] = useState("")
  const [enabled, setEnabled] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    const locked = lockedWorkflowId || initial?.workflowId || ""
    setWorkflowId(locked || workflows[0]?.id || "")
    setName(initial?.name || "")
    setScheduleType(initial?.scheduleType || "recurring")
    setTimezone(initial?.timezone || guessBrowserTimezone())
    setEnabled(initial?.enabled !== false)
    const initialCron = initial?.cron || "0 0 * * *"
    const matched = RECURRENCE_PRESETS.find((p) => p.cron && p.cron === initialCron)
    setPresetId(matched?.id || (initial?.cron ? "custom" : "daily"))
    setCron(initialCron)
    setRunAtLocal(
      initial?.runAt ? toDateTimeLocalValue(new Date(initial.runAt)) : toDateTimeLocalValue(new Date()),
    )
    setEndsAtLocal(initial?.endsAt ? toDateTimeLocalValue(new Date(initial.endsAt)) : "")
  }, [open, initial, lockedWorkflowId, workflows])

  const cronPreview = useMemo(() => {
    if (scheduleType === "once") return "Runs once at the selected date and time"
    return cron.trim() ? describeCron(cron.trim()) : ""
  }, [cron, scheduleType])

  const handlePresetChange = (id: string) => {
    setPresetId(id)
    const preset = RECURRENCE_PRESETS.find((p) => p.id === id)
    if (preset && preset.cron) setCron(preset.cron)
  }

  const handleSave = async () => {
    const targetWorkflowId = lockedWorkflowId || workflowId
    if (!targetWorkflowId) {
      toast.error("Select a workflow")
      return
    }
    setSaving(true)
    try {
      const payload =
        scheduleType === "once"
          ? {
              scheduleType: "once" as const,
              runAt: localValueToIso(runAtLocal) || undefined,
              timezone,
              name: name.trim() || undefined,
              enabled,
            }
          : {
              scheduleType: "recurring" as const,
              cron_expression: cron.trim(),
              timezone,
              name: name.trim() || undefined,
              enabled,
              endsAt: endsAtLocal ? localValueToIso(endsAtLocal) || undefined : undefined,
            }

      if (scheduleType === "once" && !payload.runAt) {
        toast.error("Choose a valid date and time")
        setSaving(false)
        return
      }
      if (scheduleType === "recurring" && !payload.cron_expression) {
        toast.error("Cron expression is required")
        setSaving(false)
        return
      }

      const saved = isEdit && initial?.scheduleId
        ? await workflowsApi.updateSchedule(targetWorkflowId, initial.scheduleId, payload)
        : await workflowsApi.createSchedule(targetWorkflowId, payload)

      toast.success(isEdit ? "Schedule updated" : "Schedule created")
      onOpenChange(false)
      onSaved?.(saved)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save schedule")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-primary" />
            {isEdit ? "Edit schedule" : "New schedule"}
          </DialogTitle>
          <DialogDescription>
            Schedule a workflow to run once or on a recurring cadence. Times use the selected timezone
            for recurring cron evaluation.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {!lockedWorkflowId ? (
            <div className="space-y-2">
              <Label>Workflow</Label>
              <Select value={workflowId} onValueChange={setWorkflowId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select workflow" />
                </SelectTrigger>
                <SelectContent>
                  {workflows.map((wf) => (
                    <SelectItem key={wf.id} value={wf.id}>
                      {wf.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="schedule-name">Name (optional)</Label>
            <Input
              id="schedule-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Nightly MSP sync"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Type</Label>
              <Select
                value={scheduleType}
                onValueChange={(v) => setScheduleType(v as WorkflowScheduleType)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="once">One-time</SelectItem>
                  <SelectItem value="recurring">Recurring</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Timezone</Label>
              <Select value={timezone} onValueChange={setTimezone}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COMMON_TIMEZONES.map((tz) => (
                    <SelectItem key={tz} value={tz}>
                      {tz}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {scheduleType === "once" ? (
            <div className="space-y-2">
              <Label htmlFor="schedule-run-at">Run at</Label>
              <Input
                id="schedule-run-at"
                type="datetime-local"
                value={runAtLocal}
                onChange={(e) => setRunAtLocal(e.target.value)}
              />
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <Label>Recurrence</Label>
                <Select value={presetId} onValueChange={handlePresetChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RECURRENCE_PRESETS.map((preset) => (
                      <SelectItem key={preset.id} value={preset.id}>
                        {preset.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {(presetId === "custom" || !RECURRENCE_PRESETS.find((p) => p.id === presetId)?.cron) && (
                <div className="space-y-2">
                  <Label htmlFor="schedule-cron">Cron expression</Label>
                  <Input
                    id="schedule-cron"
                    className="font-mono"
                    value={cron}
                    onChange={(e) => {
                      setPresetId("custom")
                      setCron(e.target.value)
                    }}
                    placeholder="0 9 * * 1-5"
                  />
                </div>
              )}
              {presetId !== "custom" && RECURRENCE_PRESETS.find((p) => p.id === presetId)?.cron ? (
                <p className="font-mono text-xs text-muted-foreground">{cron}</p>
              ) : null}
              <div className="space-y-2">
                <Label htmlFor="schedule-ends-at">Ends at (optional)</Label>
                <Input
                  id="schedule-ends-at"
                  type="datetime-local"
                  value={endsAtLocal}
                  onChange={(e) => setEndsAtLocal(e.target.value)}
                />
              </div>
            </>
          )}

          {cronPreview ? (
            <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
              {cronPreview}
            </p>
          ) : null}

          <div className="space-y-2">
            <Label>Status</Label>
            <Select
              value={enabled ? "enabled" : "disabled"}
              onValueChange={(v) => setEnabled(v === "enabled")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="enabled">Enabled</SelectItem>
                <SelectItem value="disabled">Disabled</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : isEdit ? (
              "Save changes"
            ) : (
              "Create schedule"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
