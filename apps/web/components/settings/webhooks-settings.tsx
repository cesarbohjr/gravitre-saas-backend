"use client"

import { useState } from "react"
import useSWR from "swr"
import { Loader2, Webhook, X } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { settingsApi } from "@/lib/api"

type OrgWebhook = {
  id: string
  url: string
  events: string[]
  status: string
}

const AVAILABLE_EVENTS = [
  "workflow.completed",
  "workflow.failed",
  "run.started",
  "run.failed",
  "run.completed",
  "approval.pending",
  "approval.completed",
  "approval.requested",
]

export function WebhooksSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<{ webhooks?: OrgWebhook[] }>(
    isAdmin ? "/api/settings/webhooks" : null,
    () => settingsApi.listWebhooks(),
    { revalidateOnFocus: false },
  )
  const [addDialog, setAddDialog] = useState(false)
  const [newUrl, setNewUrl] = useState("")
  const [selectedEvents, setSelectedEvents] = useState<string[]>([])
  const [isAdding, setIsAdding] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const webhooks = data?.webhooks ?? []

  const handleAddWebhook = async () => {
    setIsAdding(true)
    try {
      await settingsApi.createWebhook({ url: newUrl.trim(), events: selectedEvents, status: "active" })
      toast.success("Webhook added")
      setNewUrl("")
      setSelectedEvents([])
      setAddDialog(false)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add webhook")
    } finally {
      setIsAdding(false)
    }
  }

  const handleDeleteWebhook = async (id: string) => {
    if (!confirm("Remove this webhook?")) return
    setDeletingId(id)
    try {
      await settingsApi.deleteWebhook(id)
      toast.success("Webhook removed")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove webhook")
    } finally {
      setDeletingId(null)
    }
  }

  if (!isAdmin) {
    return <p className="text-sm text-muted-foreground">Admin or owner permission is required to manage webhooks.</p>
  }
  if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading webhooks…</p>
  if (error) {
    return (
      <div role="alert" className="space-y-3">
        <p className="text-sm">Could not load webhooks.</p>
        <Button variant="outline" className="min-h-11" onClick={() => void mutate()}>Retry webhooks</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6" aria-label="Webhooks">
      {webhooks.length === 0 ? (
        <div className="rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-2)] p-8 text-center">
          <Webhook className="mx-auto mb-3 h-8 w-8 text-muted-foreground/60" />
          <p className="text-sm font-medium">No webhooks configured yet</p>
          <p className="mt-1 text-xs text-muted-foreground">Add an outbound endpoint to receive workflow and approval events.</p>
        </div>
      ) : webhooks.map((webhook) => (
        <div key={webhook.id} className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <code className="break-all text-xs">{webhook.url}</code>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] capitalize text-muted-foreground">{webhook.status || "active"}</span>
              <Button variant="ghost" className="min-h-11" disabled={deletingId === webhook.id} onClick={() => void handleDeleteWebhook(webhook.id)}>
                {deletingId === webhook.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <X className="h-3 w-3" />}
              </Button>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(webhook.events || []).map((event) => (
              <span key={event} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{event}</span>
            ))}
          </div>
        </div>
      ))}
      <Button className="min-h-11 gap-2" onClick={() => setAddDialog(true)}>
        <Webhook className="h-3.5 w-3.5" />
        Add webhook
      </Button>
      <Dialog open={addDialog} onOpenChange={setAddDialog}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add webhook</DialogTitle>
            <DialogDescription>Configure a new outbound webhook endpoint.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label htmlFor="webhook-url" className="text-xs font-medium text-muted-foreground">Webhook URL</label>
              <Input id="webhook-url" type="url" value={newUrl} onChange={(event) => setNewUrl(event.target.value)} className="min-h-11" />
            </div>
            <fieldset className="space-y-2">
              <legend className="text-xs font-medium text-muted-foreground">Events to subscribe</legend>
              {AVAILABLE_EVENTS.map((event) => (
                <label key={event} className="flex min-h-11 items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(event)}
                    onChange={(eventChange) => {
                      setSelectedEvents((current) => eventChange.target.checked ? [...current, event] : current.filter((name) => name !== event))
                    }}
                  />
                  {event}
                </label>
              ))}
            </fieldset>
          </div>
          <DialogFooter className="flex-wrap gap-2">
            <Button variant="outline" className="min-h-11" onClick={() => setAddDialog(false)}>Cancel</Button>
            <Button className="min-h-11" onClick={() => void handleAddWebhook()} disabled={isAdding || !newUrl || selectedEvents.length === 0}>
              {isAdding ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add webhook"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
