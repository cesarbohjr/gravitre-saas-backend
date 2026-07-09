"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { notificationsApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Loader2, Save } from "lucide-react"
import { toast } from "sonner"

const EVENT_LABELS: Record<string, string> = {
  run_completed: "Workflow run completed",
  run_failed: "Workflow run failed",
  approval_needed: "Approval required",
  assignment_changed: "Assignment changed",
  scheduled_run_completed: "Scheduled run completed",
  scheduled_run_failed: "Scheduled run failed",
  task_completed: "Chat task completed",
}

type EventPreference = { bell_enabled: boolean; email_enabled: boolean }

export function EventNotificationPreferences() {
  const { data, mutate, isLoading } = useSWR("notification-event-preferences", () =>
    notificationsApi.getPreferences(),
  )
  const [draft, setDraft] = useState<Record<string, EventPreference>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (data?.preferences) {
      setDraft(data.preferences)
    }
  }, [data?.preferences])

  const handleSave = async () => {
    setSaving(true)
    try {
      await notificationsApi.updatePreferences(draft)
      await mutate()
      toast.success("Notification preferences saved")
    } catch {
      toast.error("Failed to save notification preferences")
    } finally {
      setSaving(false)
    }
  }

  if (isLoading && !Object.keys(draft).length) {
    return <p className="text-sm text-muted-foreground">Loading notification preferences…</p>
  }

  return (
    <div className="space-y-4 rounded-lg border border-border bg-secondary/20 p-4">
      <div>
        <p className="text-sm font-medium text-foreground">Event notifications</p>
        <p className="text-xs text-muted-foreground">
          Control bell and email alerts per event. Your inbox always keeps a complete record.
        </p>
      </div>
      <div className="space-y-3">
        {Object.entries(EVENT_LABELS).map(([eventType, label]) => {
          const pref = draft[eventType] ?? { bell_enabled: true, email_enabled: false }
          return (
            <div
              key={eventType}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md border border-border/70 bg-background/60 px-3 py-2"
            >
              <span className="text-sm text-foreground">{label}</span>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={pref.bell_enabled}
                  onChange={(event) =>
                    setDraft((prev) => ({
                      ...prev,
                      [eventType]: { ...pref, bell_enabled: event.target.checked },
                    }))
                  }
                />
                Bell
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={pref.email_enabled}
                  onChange={(event) =>
                    setDraft((prev) => ({
                      ...prev,
                      [eventType]: { ...pref, email_enabled: event.target.checked },
                    }))
                  }
                />
                Email
              </label>
            </div>
          )
        })}
      </div>
      <Button size="sm" className="gap-2" onClick={handleSave} disabled={saving}>
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
        Save event preferences
      </Button>
    </div>
  )
}
