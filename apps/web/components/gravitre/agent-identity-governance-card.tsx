"use client"

import { useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { agentIdentityApi, type AgentIdentityRecord } from "@/lib/api"
import { Loader2 } from "lucide-react"

const TRUST_LEVELS = ["read_only", "write_with_approval", "autonomous"] as const

export function AgentIdentityGovernanceCard({ agentId, canEdit }: { agentId: string; canEdit: boolean }) {
  const { data, mutate, isLoading, error } = useSWR(
    agentId ? `agent-identity-${agentId}` : null,
    () => agentIdentityApi.get(agentId),
  )
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<Partial<AgentIdentityRecord>>({})

  const identity = data?.identity
  const effective = data?.effective
  const usage = data?.usageToday

  const draft = { ...identity, ...form }

  async function save() {
    if (!canEdit) return
    setSaving(true)
    try {
      await agentIdentityApi.upsert(agentId, {
        trustLevel: draft.trustLevel,
        maxSpendUsdPerDay: draft.maxSpendUsdPerDay,
        maxActionsPerDay: draft.maxActionsPerDay,
        allowedToolPatterns: draft.allowedToolPatterns ?? [],
        allowedActionKinds: draft.allowedActionKinds ?? ["read", "write"],
        canDelegate: draft.canDelegate ?? false,
        approvalRuleOverrides: draft.approvalRuleOverrides ?? {},
      })
      await mutate()
      setForm({})
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Agent identity &amp; governance</h2>
        <p className="text-sm text-muted-foreground">
          Spend limits, tool scope, and delegation — enforced via write-authority gates.
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading identity record…
        </div>
      ) : null}

      {error ? (
        <p className="text-sm text-destructive">Could not load agent identity settings.</p>
      ) : null}

      {usage ? (
        <div className="rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          Today: {usage.actions} actions · ${usage.spendUsd.toFixed(4)} spend
          {effective?.activeDelegationId ? " · active delegation" : ""}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="trust-level">Trust level</Label>
          <select
            id="trust-level"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            disabled={!canEdit}
            value={draft.trustLevel ?? "write_with_approval"}
            onChange={(e) => setForm((f) => ({ ...f, trustLevel: e.target.value }))}
          >
            {TRUST_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="spend-limit">Daily spend limit (USD)</Label>
          <Input
            id="spend-limit"
            type="number"
            min={0}
            step={0.01}
            disabled={!canEdit}
            placeholder="No limit"
            value={draft.maxSpendUsdPerDay ?? ""}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                maxSpendUsdPerDay: e.target.value === "" ? undefined : Number(e.target.value),
              }))
            }
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="tool-patterns">Allowed tool patterns (comma-separated globs)</Label>
          <Input
            id="tool-patterns"
            disabled={!canEdit}
            placeholder="hubspot.*, slack.post_message"
            value={(draft.allowedToolPatterns ?? []).join(", ")}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                allowedToolPatterns: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              }))
            }
          />
        </div>
        <div className="flex items-center gap-2 sm:col-span-2">
          <input
            id="can-delegate"
            type="checkbox"
            disabled={!canEdit}
            checked={Boolean(draft.canDelegate)}
            onChange={(e) => setForm((f) => ({ ...f, canDelegate: e.target.checked }))}
          />
          <Label htmlFor="can-delegate">Allow delegation grants to this agent</Label>
        </div>
      </div>

      {canEdit ? (
        <Button size="sm" onClick={save} disabled={saving}>
          {saving ? "Saving…" : identity ? "Update identity" : "Create identity record"}
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">Org admin required to edit identity settings.</p>
      )}
    </div>
  )
}
