"use client"

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { agentIdentityApi, type AgentIdentityRecord } from "@/lib/api"

export function AgentPolicyEditor({
  agentId,
  record,
  onSaved,
}: {
  agentId: string
  record: AgentIdentityRecord | null
  onSaved: (record: AgentIdentityRecord) => void
}) {
  const [open, setOpen] = useState(false)
  const [trust, setTrust] = useState("read_only")
  const [limits, setLimits] = useState({ actions: "", tokens: "", spend: "" })
  const [baseline, setBaseline] = useState<AgentIdentityRecord | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const busy = useRef(false)
  function changeOpen(next: boolean) {
    if (busy.current) return
    if (next) {
      setBaseline(record)
      setTrust(record?.trustLevel || "read_only")
      setLimits({
        actions: record?.maxActionsPerDay?.toString() ?? "",
        tokens: record?.maxTokensPerDay?.toString() ?? "",
        spend: record?.maxSpendUsdPerDay?.toString() ?? "",
      })
      setError(null)
    }
    setOpen(next)
  }
  async function save() {
    if (busy.current) return
    const values = [limits.actions, limits.tokens, limits.spend]
    const previous = [
      baseline?.maxActionsPerDay,
      baseline?.maxTokensPerDay,
      baseline?.maxSpendUsdPerDay,
    ]
    if (
      values.some((value, i) =>
        value.trim()
          ? !Number.isFinite(Number(value)) ||
            Number(value) < 0 ||
            (i < 2 && !Number.isSafeInteger(Number(value)))
          : previous[i] != null,
      )
    ) {
      setError(
        "Enter non-negative limits; actions and tokens must be whole numbers. Existing limits cannot be cleared through this API.",
      )
      return
    }
    busy.current = true
    setSaving(true)
    setError(null)
    try {
      const result = await agentIdentityApi.upsert(agentId, {
        ...baseline,
        trustLevel: trust,
        // PUT initializes absent arrays: preserve all unrelated policy fields explicitly.
        allowedToolPatterns: baseline?.allowedToolPatterns ?? [],
        allowedActionKinds: baseline?.allowedActionKinds ?? ["read"],
        allowedDataScopes: baseline?.allowedDataScopes ?? [],
        approvalRuleOverrides: baseline?.approvalRuleOverrides ?? {},
        ...(limits.actions.trim()
          ? { maxActionsPerDay: Number(limits.actions) }
          : {}),
        ...(limits.tokens.trim()
          ? { maxTokensPerDay: Number(limits.tokens) }
          : {}),
        ...(limits.spend.trim()
          ? { maxSpendUsdPerDay: Number(limits.spend) }
          : {}),
      })
      onSaved(result.identity)
      setOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save policy")
    } finally {
      busy.current = false
      setSaving(false)
    }
  }
  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button className="min-h-11" variant="outline">
          Edit policy
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Agent execution policy</DialogTitle>
          <DialogDescription>
            Set the stored trust level and daily ceilings. Organization approval
            rules, connector permissions and active delegations still apply.
          </DialogDescription>
        </DialogHeader>
        <fieldset disabled={saving} className="min-w-0 space-y-5">
          <label className="block space-y-2 text-sm">
            <span className="font-medium">Trust level</span>
            <select
              className="min-h-11 w-full rounded-md border bg-background px-3"
              value={trust}
              onChange={(e) => setTrust(e.target.value)}
            >
              {!["read_only", "write_with_approval", "autonomous"].includes(
                trust,
              ) && <option value={trust}>{trust}</option>}
              <option value="read_only">Read only</option>
              <option value="write_with_approval">Act with approval</option>
              <option value="autonomous">Act within policy</option>
            </select>
          </label>
          <div className="divide-y border-y border-[color:var(--g-border-default)]">
            {(
              [
                ["actions", "Actions per day"],
                ["tokens", "Tokens per day"],
                ["spend", "Spend per day (USD)"],
              ] as const
            ).map(([key, label]) => (
              <label
                key={key}
                className="grid gap-2 py-4 text-sm sm:grid-cols-2 sm:items-center"
              >
                <span>{label}</span>
                <input
                  aria-label={label}
                  className="min-h-11 min-w-0 rounded-md border bg-background px-3"
                  type="number"
                  min="0"
                  step={key === "spend" ? "any" : "1"}
                  value={limits[key]}
                  onChange={(e) =>
                    setLimits({ ...limits, [key]: e.target.value })
                  }
                  placeholder="Not set"
                />
              </label>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Tool patterns, action kinds, data scopes, delegation settings and
            approval overrides are preserved. Blank new limits stay unset;
            existing limits cannot be removed here.
          </p>
        </fieldset>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button
            className="min-h-11"
            variant="outline"
            disabled={saving}
            onClick={() => changeOpen(false)}
          >
            Cancel
          </Button>
          <Button
            className="min-h-11"
            disabled={saving}
            onClick={() => void save()}
          >
            {saving ? "Saving…" : "Save policy"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
