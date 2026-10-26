"use client"

import { confirmDialog } from "@/components/agents/overlays/confirm"
import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "@/components/agents/overlays/toast"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { connectorsApi } from "@/lib/api"
import { agentToolPermissionsApi, type AgentToolPermission } from "@/lib/agent-tool-permissions"

const formatDate = (value: string | null) => value ? new Date(value).toLocaleString() : "No expiry"

function permissionStatus(permission: AgentToolPermission) {
  return permission.expiresAt && new Date(permission.expiresAt).getTime() <= Date.now()
    ? "Expired" : "Granted"
}

/** Existing agent Governance tab: live, per-agent, admin-only connector permission management. */
export function AgentToolPermissionsPanel({ agentId, canEdit }: { agentId: string; canEdit: boolean }) {
  const { data: permissions, error, isLoading, mutate } = useSWR(
    canEdit && agentId ? ["agent-tool-permissions", agentId] : null,
    () => agentToolPermissionsApi.list(agentId),
    { revalidateOnFocus: true },
  )
  const { data: connections, error: connectorError } = useSWR(
    canEdit ? ["agent-tool-permission-connectors", agentId] : null,
    () => connectorsApi.list(),
  )
  const connected = useMemo(
    () => (connections?.connectors ?? []).filter((connector) => connector.status === "active"),
    [connections],
  )
  const [connectorId, setConnectorId] = useState("")
  const [scopesText, setScopesText] = useState("")
  const [expiryHours, setExpiryHours] = useState("24")
  const [busy, setBusy] = useState(false)

  const selected = connected.find((connector) => connector.id === connectorId)
  const scopes = scopesText.split(",").map((value) => value.trim()).filter(Boolean)
  const validScopes = scopes.length > 0 && scopes.every((value) => !value.includes("*") && value.length <= 128)
  const hours = Number(expiryHours)
  const validHours = Number.isFinite(hours) && hours > 0 && hours <= 720

  async function grant() {
    if (!canEdit || !selected || !validScopes || !validHours) return
    if (
      !(await confirmDialog({
        title: `Grant access to ${selected.name} for ${hours} hour(s)?`,
        description: `Scopes: ${scopes.join(", ")}. Confirm only permissions required for its task.`,
        confirmLabel: "Grant access",
        tone: "default",
      }))
    )
      return
    setBusy(true)
    try {
      await agentToolPermissionsApi.grant(agentId, {
        connectorId: selected.id,
        scopes,
        expiresAt: new Date(Date.now() + hours * 3_600_000).toISOString(),
      })
      await mutate()
      setScopesText("")
      setConnectorId("")
      toast.success("Agent connector permission granted")
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : "Could not grant permission")
    } finally {
      setBusy(false)
    }
  }

  async function revoke(permission: AgentToolPermission) {
    if (!canEdit) return
    if (!(await confirmDialog({ title: "Revoke this connector permission?", description: "Future tool requests from this agent will be denied.", confirmLabel: "Revoke" }))) return
    setBusy(true)
    try {
      await agentToolPermissionsApi.revoke(agentId, permission.id)
      await mutate()
      toast.success("Agent connector permission revoked")
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : "Could not revoke permission")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-5" aria-labelledby="agent-tool-permissions-heading">
      <div>
        <h2 id="agent-tool-permissions-heading" className="text-lg font-semibold">Connector tool permissions</h2>
        <p className="text-sm text-muted-foreground">
          Explicit agent-level access to connected systems. Connector availability does not imply permission.
          These grants are additional to identity, organization and human-approval policies.
        </p>
      </div>
      {!canEdit ? (
        <p className="text-sm text-muted-foreground">Organization admin access is required to view or change tool grants.</p>
      ) : (
        <>
          {isLoading && <p role="status" className="text-sm text-muted-foreground">Loading current grants…</p>}
          {error && <p role="alert" className="text-sm text-destructive">
            Could not load grants. {error instanceof Error ? error.message : ""}
          </p>}
          {!isLoading && !error && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">Current grants</h3>
              {(permissions ?? []).length === 0 && (
                <p className="text-sm text-muted-foreground">No explicit connector tool permissions recorded.</p>
              )}
              {(permissions ?? []).map((permission) => (
                <div key={permission.id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border p-3">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-medium">{permission.connectorType || connected.find((c) => c.id === permission.connectorId)?.name || "Connector"} · {permissionStatus(permission)}</p>
                    <p className="break-all text-xs text-muted-foreground">Connector: {permission.connectorId || "Type scoped"}</p>
                    <p className="break-words text-xs text-muted-foreground">Scopes: {permission.scopes.join(", ")}</p>
                    <p className="text-xs text-muted-foreground">Expires: {formatDate(permission.expiresAt)}</p>
                  </div>
                  <Button type="button" size="sm" variant="outline" disabled={busy}
                    onClick={() => void revoke(permission)}>Revoke</Button>
                </div>
              ))}
            </div>
          )}
          <div className="space-y-3 border-t border-border pt-4">
            <h3 className="text-sm font-semibold">Grant a limited permission</h3>
            {connectorError && <p role="alert" className="text-sm text-destructive">Unable to load connected systems.</p>}
            <div className="space-y-1">
              <Label htmlFor="agent-permission-connector">Connected system</Label>
              <select id="agent-permission-connector" value={connectorId}
                onChange={(event) => setConnectorId(event.target.value)} disabled={busy || connected.length === 0}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="">Select an active connection</option>
                {connected.map((connector) => (
                  <option key={connector.id} value={connector.id}>{connector.name} ({connector.vendor})</option>
                ))}
              </select>
              {connected.length === 0 && !connectorError && <p className="text-xs text-muted-foreground">Connect a system before granting agent access.</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="agent-permission-scopes">Allowed scopes (comma-separated)</Label>
              <Input id="agent-permission-scopes" value={scopesText} disabled={busy}
                placeholder="e.g. contacts.read" onChange={(event) => setScopesText(event.target.value)} />
              <p className="text-xs text-muted-foreground">Specify only supported, required scopes. Wildcard grants are not offered.</p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="agent-permission-expiry">Expires in hours (1–720)</Label>
              <Input id="agent-permission-expiry" type="number" min={1} max={720} step={1}
                value={expiryHours} disabled={busy} onChange={(event) => setExpiryHours(event.target.value)} />
            </div>
            <Button type="button" size="sm" disabled={busy || !selected || !validScopes || !validHours}
              onClick={() => void grant()}>Grant permission</Button>
          </div>
        </>
      )}
    </section>
  )
}
