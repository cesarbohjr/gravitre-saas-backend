"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { Check, Info, Loader2, Save, Shield } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { accountIntelligenceApi, type SourceDataGovernance } from "@/lib/api"

/** Customer-facing systems the customer-context paths can read (mirrors the backend list). */
const CUSTOMER_SOURCES = [
  { id: "hubspot", label: "HubSpot" },
  { id: "salesforce", label: "Salesforce" },
  { id: "zendesk", label: "Zendesk" },
  { id: "intercom", label: "Intercom" },
  { id: "freshdesk", label: "Freshdesk" },
  { id: "helpscout", label: "Help Scout" },
  { id: "front", label: "Front" },
  { id: "gmail", label: "Gmail" },
  { id: "microsoft365", label: "Microsoft 365" },
] as const

/** Shown only with NEXT_PUBLIC_SOURCE_GOVERNANCE_UI=true until the customer-context paths ship. */
export const SOURCE_GOVERNANCE_UI_ENABLED = process.env.NEXT_PUBLIC_SOURCE_GOVERNANCE_UI === "true"

function sorted(values: string[]) {
  return [...values].map(String).sort()
}

export function SourceGovernanceSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, mutate, isLoading, error } = useSWR(
    "/api/settings/source-governance",
    () => accountIntelligenceApi.sourceGovernance(),
    { revalidateOnFocus: false },
  )
  const remote = data?.sourceDataGovernance
  const [enabled, setEnabled] = useState(false)
  const [connectors, setConnectors] = useState<string[]>([])
  const [retention, setRetention] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!remote) return
    setEnabled(remote.customerContext.enabled)
    setConnectors(remote.customerContext.connectors)
    setRetention(Object.fromEntries(Object.entries(remote.retentionDays).map(([k, v]) => [k, String(v)])))
  }, [remote])

  const policy = useMemo<SourceDataGovernance>(() => {
    const retentionDays: Record<string, number> = {}
    for (const [vendor, raw] of Object.entries(retention)) {
      const days = Number.parseInt(raw, 10)
      if (Number.isFinite(days) && days > 0) retentionDays[vendor] = days
    }
    return { customerContext: { enabled, connectors: enabled ? connectors : [] }, retentionDays }
  }, [enabled, connectors, retention])

  const dirty = useMemo(() => {
    if (!remote) return false
    return (
      remote.customerContext.enabled !== policy.customerContext.enabled ||
      JSON.stringify(sorted(remote.customerContext.connectors)) !== JSON.stringify(sorted(policy.customerContext.connectors)) ||
      JSON.stringify(Object.entries(remote.retentionDays).sort()) !== JSON.stringify(Object.entries(policy.retentionDays).sort())
    )
  }, [remote, policy])

  const save = async () => {
    setSaving(true)
    try {
      await accountIntelligenceApi.saveSourceGovernance(policy)
      await mutate()
      setSaved(true)
      toast.success(policy.customerContext.enabled ? "Customer context switched on" : "Customer data settings saved")
      setTimeout(() => setSaved(false), 2000)
    } catch {
      toast.error("Couldn't save customer data settings.")
    } finally {
      setSaving(false)
    }
  }

  if (isLoading && !remote) {
    return (
      <p role="status" className="flex items-center gap-2 pt-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading customer data settings…
      </p>
    )
  }
  if (error && !remote) {
    return <p className="pt-6 text-sm text-muted-foreground">Customer data settings couldn&apos;t load.</p>
  }

  return (
    <section aria-labelledby="source-governance-heading" className="space-y-4 border-t border-divide pt-6">
      <div>
        <h3 id="source-governance-heading" className="text-sm font-medium text-foreground">Customer data</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Whether Gravitre may keep what customers say in your support and sales systems, and how long indexed
          documents are kept. Off by default.
        </p>
      </div>

      <div className="flex items-start gap-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] p-3">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="space-y-1.5 text-xs text-muted-foreground">
          <p>
            When on, messages from <span className="font-medium text-foreground">customers</span> in the systems you pick
            can be linked to their account and judged for tone, urgency, churn-risk language and similar signals, each
            with the words quoted as evidence.
          </p>
          <p>Internal chat and messages from your own colleagues are never read for this.</p>
          <p>Disconnecting a system removes what Gravitre kept from it.</p>
        </div>
      </div>

      <label
        className={`flex items-center justify-between rounded-lg border border-divide bg-[color:var(--g-surface-2)] p-3 ${
          isAdmin ? "cursor-pointer hover:bg-secondary/50" : "opacity-70"
        }`}
      >
        <span className="flex items-center gap-3">
          <Shield className="h-4 w-4 text-muted-foreground" />
          <span>
            <span className="block text-sm font-medium text-foreground">Use customer context</span>
            <span className="block text-xs text-muted-foreground">Leave every system unticked to cover all connected ones</span>
          </span>
        </span>
        <input
          type="checkbox"
          aria-label="Use customer context"
          checked={enabled}
          disabled={!isAdmin || saving}
          onChange={(e) => setEnabled(e.target.checked)}
        />
      </label>

      {enabled ? (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Customer context systems">
          {CUSTOMER_SOURCES.map((source) => {
            const active = connectors.includes(source.id)
            return (
              <button
                key={source.id}
                type="button"
                aria-pressed={active}
                disabled={!isAdmin || saving}
                onClick={() =>
                  setConnectors((prev) => (active ? prev.filter((id) => id !== source.id) : [...prev, source.id]))
                }
                className={`min-h-11 rounded-md border px-3 text-xs ${
                  active ? "border-foreground/30 bg-foreground/5 text-foreground" : "border-border text-muted-foreground"
                }`}
              >
                {source.label}
              </button>
            )
          })}
        </div>
      ) : null}

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground">Keep indexed documents for (days)</p>
        <p className="text-xs text-muted-foreground">Empty keeps them until the source is disconnected. 7 to 3650 days.</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {CUSTOMER_SOURCES.map((source) => (
            <label key={source.id} className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
              {source.label}
              <input
                inputMode="numeric"
                aria-label={`${source.label} retention days`}
                className="h-11 w-24 rounded-md border border-border bg-transparent px-2 text-base text-foreground sm:text-sm"
                value={retention[source.id] ?? ""}
                disabled={!isAdmin || saving}
                onChange={(e) => setRetention((prev) => ({ ...prev, [source.id]: e.target.value.replace(/\D/g, "") }))}
              />
            </label>
          ))}
        </div>
      </div>

      {isAdmin ? (
        <Button size="sm" className="min-h-11 gap-2" onClick={() => void save()} disabled={saving || !dirty}>
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <Check className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
          {saved ? "Saved" : "Save customer data settings"}
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">Only organization admins can change this setting.</p>
      )}
    </section>
  )
}
