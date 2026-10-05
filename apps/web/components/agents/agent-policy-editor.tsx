"use client"

import { useRef, useState } from "react"
import useSWR from "swr"
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
import {
  agentIdentityApi,
  agentsApi,
  type AgentIdentityRecord,
} from "@/lib/api"

const ACTION_KINDS = ["read", "write", "delete"] as const
const OVERRIDE_OPTIONS = [
  ["always_approve", "Always needs approval"],
  ["always_deny", "Always denied"],
  ["auto_run", "Runs without approval"],
] as const

function listText(values: string[] | undefined) {
  return (values ?? []).join("\n")
}
function parseLines(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}
function overrideText(overrides: Record<string, string> | undefined) {
  return Object.entries(overrides ?? {})
    .map(([key, value]) => `${key}=${value}`)
    .join("\n")
}
function parseOverrides(value: string) {
  const next: Record<string, string> = {}
  for (const line of value.split("\n")) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const at = trimmed.indexOf("=")
    if (at < 1) return null
    const key = trimmed.slice(0, at).trim()
    const option = trimmed.slice(at + 1).trim()
    if (!OVERRIDE_OPTIONS.some(([id]) => id === option)) return null
    next[key] = option
  }
  return next
}

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
  const [patterns, setPatterns] = useState("")
  const [scopes, setScopes] = useState("")
  const [kinds, setKinds] = useState<string[]>(["read"])
  const [overrides, setOverrides] = useState("")
  const [canDelegate, setCanDelegate] = useState(false)
  const [baseline, setBaseline] = useState<AgentIdentityRecord | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [grantReason, setGrantReason] = useState("")
  const [granteeId, setGranteeId] = useState("")
  const [expires, setExpires] = useState("60")
  const [grantBusy, setGrantBusy] = useState(false)
  const [revokeId, setRevokeId] = useState<string | null>(null)
  const busy = useRef(false)
  const {
    data: grantsData,
    error: grantsError,
    mutate: mutateGrants,
  } = useSWR(open ? `agent/${agentId}/delegations` : null, () =>
    agentIdentityApi.listDelegations(agentId),
  )
  const { data: agentsData } = useSWR(open ? "policy/agents" : null, () =>
    agentsApi.list(),
  )
  const grants = grantsData?.grants ?? []
  const agents = agentsData?.agents ?? []
  function changeOpen(next: boolean) {
    if (busy.current || grantBusy || revokeId) return
    if (next) {
      setBaseline(record)
      setTrust(record?.trustLevel || "read_only")
      setLimits({
        actions: record?.maxActionsPerDay?.toString() ?? "",
        tokens: record?.maxTokensPerDay?.toString() ?? "",
        spend: record?.maxSpendUsdPerDay?.toString() ?? "",
      })
      setPatterns(listText(record?.allowedToolPatterns))
      setScopes(listText(record?.allowedDataScopes))
      setKinds(record?.allowedActionKinds?.length ? record.allowedActionKinds : ["read"])
      setOverrides(overrideText(record?.approvalRuleOverrides))
      setCanDelegate(Boolean(record?.canDelegate))
      setGrantReason("")
      setGranteeId("")
      setExpires("60")
      setError(null)
    }
    setOpen(next)
  }
  function parseLimit(value: string, integer: boolean) {
    if (!value.trim()) return null
    const number = Number(value)
    if (!Number.isFinite(number) || number < 0) return undefined
    if (integer && !Number.isSafeInteger(number)) return undefined
    return number
  }
  async function save() {
    if (busy.current) return
    const actions = parseLimit(limits.actions, true)
    const tokens = parseLimit(limits.tokens, true)
    const spend = parseLimit(limits.spend, false)
    const nextOverrides = parseOverrides(overrides)
    if (actions === undefined || tokens === undefined || spend === undefined) {
      setError("Enter non-negative limits; actions and tokens must be whole numbers.")
      return
    }
    if (!nextOverrides) {
      setError("Approval overrides must use action=always_approve|always_deny|auto_run.")
      return
    }
    busy.current = true
    setSaving(true)
    setError(null)
    try {
      const result = await agentIdentityApi.upsert(agentId, {
        ...baseline,
        trustLevel: trust,
        allowedToolPatterns: parseLines(patterns),
        allowedActionKinds: kinds,
        allowedDataScopes: parseLines(scopes),
        approvalRuleOverrides: nextOverrides,
        canDelegate,
        maxActionsPerDay: actions,
        maxTokensPerDay: tokens,
        maxSpendUsdPerDay: spend,
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
  async function grant() {
    if (grantBusy || !granteeId.trim()) {
      setError("Choose a grantee agent.")
      return
    }
    const minutes = Number(expires)
    if (!Number.isSafeInteger(minutes) || minutes < 1) {
      setError("Expiration must be a whole number of minutes.")
      return
    }
    setGrantBusy(true)
    setError(null)
    try {
      const result = await agentIdentityApi.createDelegation(agentId, {
        grantorAgentId: agentId,
        granteeAgentId: granteeId.trim(),
        reason: grantReason.trim() || undefined,
        expiresInMinutes: minutes,
        delegatedPermissions: { trustLevel: trust },
      })
      if (!result.grant) {
        throw new Error("The server did not return a saved delegation grant.")
      }
      setGrantReason("")
      await mutateGrants()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the delegation grant")
    } finally {
      setGrantBusy(false)
    }
  }
  async function revoke(grantId: string) {
    if (revokeId) return
    setRevokeId(grantId)
    setError(null)
    try {
      await agentIdentityApi.revokeDelegation(agentId, grantId)
      await mutateGrants()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke the delegation grant")
    } finally {
      setRevokeId(null)
    }
  }
  const locked = saving || grantBusy || Boolean(revokeId)
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
            Set stored trust, scopes, daily ceilings, approval overrides and
            delegation grants. Organization rules and connector permissions
            still apply.
          </DialogDescription>
        </DialogHeader>
        <fieldset disabled={locked} className="min-w-0 space-y-5">
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
            Blank ceilings remove an existing limit. Zero remains a stored
            zero.
          </p>
          <label className="block space-y-2 text-sm">
            <span className="font-medium">Allowed tool patterns</span>
            <textarea
              aria-label="Allowed tool patterns"
              className="min-h-24 w-full rounded-md border bg-background px-3 py-2"
              value={patterns}
              onChange={(e) => setPatterns(e.target.value)}
              placeholder="hubspot.*&#10;slack.messages.send"
            />
          </label>
          <fieldset className="space-y-2 text-sm">
            <legend className="font-medium">Allowed action kinds</legend>
            <div className="flex flex-wrap gap-3">
              {ACTION_KINDS.map((kind) => (
                <label key={kind} className="flex min-h-11 items-center gap-2">
                  <input
                    type="checkbox"
                    checked={kinds.includes(kind)}
                    onChange={(e) =>
                      setKinds((current) =>
                        e.target.checked
                          ? [...current, kind]
                          : current.filter((item) => item !== kind),
                      )
                    }
                  />
                  {kind}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="block space-y-2 text-sm">
            <span className="font-medium">Allowed data scopes</span>
            <textarea
              aria-label="Allowed data scopes"
              className="min-h-20 w-full rounded-md border bg-background px-3 py-2"
              value={scopes}
              onChange={(e) => setScopes(e.target.value)}
              placeholder="org&#10;crm.contacts"
            />
          </label>
          <label className="block space-y-2 text-sm">
            <span className="font-medium">Approval rule overrides</span>
            <textarea
              aria-label="Approval rule overrides"
              className="min-h-20 w-full rounded-md border bg-background px-3 py-2"
              value={overrides}
              onChange={(e) => setOverrides(e.target.value)}
              placeholder="write=always_approve"
            />
          </label>
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={canDelegate}
              onChange={(e) => setCanDelegate(e.target.checked)}
            />
            This agent can receive delegation grants
          </label>
          <section className="space-y-3 border-t border-[color:var(--g-border-default)] pt-4">
            <h3 className="text-sm font-medium">Delegation grants</h3>
            {grantsError ? (
              <p role="alert" className="text-sm text-destructive">
                Delegation grants could not be loaded.
              </p>
            ) : grants.length ? (
              <ul className="divide-y border-y">
                {grants.map((grant) => {
                  const id = String(grant.id ?? "")
                  const revoked = Boolean(grant.revokedAt ?? grant.revoked_at)
                  return (
                    <li key={id || String(grant.createdAt)} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                      <span>
                        {String(grant.granteeAgentId ?? grant.grantee_agent_id ?? "Unknown grantee")}
                        {revoked ? " · Revoked" : ""}
                      </span>
                      {id && !revoked ? (
                        <Button
                          type="button"
                          variant="ghost"
                          className="min-h-11"
                          disabled={locked}
                          onClick={() => void revoke(id)}
                        >
                          {revokeId === id ? "Revoking…" : "Revoke"}
                        </Button>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No grants returned.</p>
            )}
            <label className="block space-y-2 text-sm">
              <span className="font-medium">Grant to agent</span>
              <select
                aria-label="Grant to agent"
                className="min-h-11 w-full rounded-md border bg-background px-3"
                value={granteeId}
                onChange={(e) => setGranteeId(e.target.value)}
              >
                <option value="">Select an agent</option>
                {agents
                  .filter((agent) => agent.id && agent.id !== agentId)
                  .map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
              </select>
            </label>
            <label className="block space-y-2 text-sm">
              <span className="font-medium">Reason</span>
              <input
                aria-label="Delegation reason"
                className="min-h-11 w-full rounded-md border bg-background px-3"
                value={grantReason}
                onChange={(e) => setGrantReason(e.target.value)}
              />
            </label>
            <label className="block space-y-2 text-sm">
              <span className="font-medium">Expires in minutes</span>
              <input
                aria-label="Expires in minutes"
                className="min-h-11 w-full rounded-md border bg-background px-3"
                type="number"
                min="1"
                value={expires}
                onChange={(e) => setExpires(e.target.value)}
              />
            </label>
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              disabled={locked}
              onClick={() => void grant()}
            >
              {grantBusy ? "Granting…" : "Create grant"}
            </Button>
          </section>
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
            disabled={locked}
            onClick={() => changeOpen(false)}
          >
            Cancel
          </Button>
          <Button
            className="min-h-11"
            disabled={locked}
            onClick={() => void save()}
          >
            {saving ? "Saving…" : "Save policy"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
