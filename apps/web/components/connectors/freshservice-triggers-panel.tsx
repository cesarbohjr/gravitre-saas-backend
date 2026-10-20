"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "sonner"
import { useState } from "react"
import { TYPE } from "@/lib/design-system"

type TriggerRow = {
  id?: string | null
  event: string
  status?: string | null
  workflow_id: string
  active?: boolean
  label?: string | null
}

type SetupPayload = {
  inbound_url: string
  webhook_secret: string
  secret_header: string
  sample_payload: Record<string, unknown>
}

type TriggersResponse = {
  triggers: TriggerRow[]
  setup: SetupPayload
}

export function FreshserviceTriggersPanel({ connectorId }: { connectorId: string }) {
  const { data, error, isLoading, mutate } = useSWR<TriggersResponse>(
    `/api/connectors/${connectorId}/freshservice-triggers`,
    fetcher,
  )
  const [draft, setDraft] = useState<TriggerRow[] | null>(null)
  const [saving, setSaving] = useState(false)

  const rows = draft ?? data?.triggers ?? []

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-muted-foreground">
        <Spinner className="h-4 w-4" />
        <span className={TYPE.body}>Loading event triggers…</span>
      </div>
    )
  }
  if (error) {
    return <p className={TYPE.body}>Event triggers could not be loaded.</p>
  }
  if (!data?.setup) return null

  const addRow = () => {
    setDraft([
      ...rows,
      { event: "ticket.updated", workflow_id: "", active: true, label: "New binding" },
    ])
  }

  const save = async () => {
    setSaving(true)
    try {
      const res = await fetch(`/api/connectors/${connectorId}/freshservice-triggers`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ triggers: rows.filter((r) => r.workflow_id.trim()) }),
      })
      if (!res.ok) throw new Error(await res.text())
      toast.success("Freshservice triggers saved")
      setDraft(null)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="space-y-4 rounded-lg border border-border/60 p-4">
      <div>
        <h3 className={TYPE.sectionTitle}>Freshservice event triggers</h3>
        <p className={`${TYPE.body} text-muted-foreground mt-1`}>
          Inbound URL and secret for Freshservice webhooks. Test delivery status is shown after Freshservice posts an event.
        </p>
      </div>
      <div className="space-y-2 text-sm">
        <div>
          <span className="text-muted-foreground">Inbound URL</span>
          <Input readOnly value={data.setup.inbound_url} className="font-mono text-xs mt-1" />
        </div>
        <div>
          <span className="text-muted-foreground">Secret header</span>
          <Input readOnly value={data.setup.secret_header} className="font-mono text-xs mt-1" />
        </div>
      </div>
      <div className="space-y-3">
        {rows.map((row, idx) => (
          <div key={row.id ?? idx} className="grid gap-2 sm:grid-cols-3">
            <Input
              placeholder="ticket.updated"
              value={row.event}
              onChange={(e) => {
                const next = [...rows]
                next[idx] = { ...row, event: e.target.value }
                setDraft(next)
              }}
            />
            <Input
              placeholder="Workflow ID"
              value={row.workflow_id}
              onChange={(e) => {
                const next = [...rows]
                next[idx] = { ...row, workflow_id: e.target.value }
                setDraft(next)
              }}
            />
            <Input
              placeholder="Status filter (optional)"
              value={row.status ?? ""}
              onChange={(e) => {
                const next = [...rows]
                next[idx] = { ...row, status: e.target.value || null }
                setDraft(next)
              }}
            />
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={addRow}>
          Add trigger
        </Button>
        <Button type="button" size="sm" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save triggers"}
        </Button>
      </div>
    </section>
  )
}
