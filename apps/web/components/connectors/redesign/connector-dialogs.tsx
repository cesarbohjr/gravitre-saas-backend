"use client"

import { useEffect, useState } from "react"
import { Loader2, Lock, Trash2 } from "lucide-react"
import { ConnectorsAlertDialog, ConnectorsBullets, ConnectorsDialog } from "@/components/connectors/overlays/dialog"
import { disconnectImpactLines, useDataRemoval } from "@/components/connectors/data-removal"
import { SYNC_INTERVALS, syncIntervalLabel, usageSentence } from "./connector-usage"

/** The fields both dialogs read, from either the hub list or the detail record. */
export type DialogConnector = {
  id: string
  name: string
  /** Vendor label ("HubSpot"). */
  type: string
  vendorKey: string
  environment?: string
  authType?: "oauth" | "apiKey" | "webhook"
  authStatus?: string
  /** Masked by the API ("••••abcd"), never the secret. */
  maskedApiKey?: string | null
  authProvider?: string | null
  syncFrequency?: string | null
  blockingReason?: string | null
  recordsSynced?: number | null
}

export type ConfigurePatch = { apiKey?: string; syncFrequency?: string }

/**
 * Configure dialog: never shows a stored secret, only replaces it; the sync
 * interval the scheduler honours; OAuth systems reconnect instead of taking a
 * key. Saves through PATCH /api/connectors/{id} via `onSave`.
 */
export function ConfigureConnectorDialog({
  connector,
  open,
  onOpenChange,
  onSave,
  onReconnect,
  missingScopeNote,
}: {
  connector: DialogConnector
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (patch: ConfigurePatch) => Promise<boolean>
  onReconnect?: () => void
  /** Who needs the missing permission ("needed by Support Triage"), when one is missing. */
  missingScopeNote?: string | null
}) {
  const isOAuth = connector.authType === "oauth"
  const current = String(connector.syncFrequency ?? "").trim() || "1h"
  const [replacing, setReplacing] = useState(false)
  const [apiKey, setApiKey] = useState("")
  const [interval, setInterval] = useState(current)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setReplacing(false)
    setApiKey("")
    setInterval(current)
  }, [open, current])

  const changed = interval !== current || (replacing && apiKey.trim().length > 0)
  const expired = connector.authStatus === "auth_expired" || connector.blockingReason === "token_expired"
  const missingScope = connector.blockingReason === "missing_scope"
  const knownInterval = SYNC_INTERVALS.some((opt) => opt.value === current)
  const method = isOAuth ? (connector.authProvider === "managed" ? "Secure sign in" : "OAuth") : connector.authType === "webhook" ? "Webhook" : "API key"

  const save = async () => {
    if (!changed || saving) return
    const patch: ConfigurePatch = {}
    if (interval !== current) patch.syncFrequency = interval
    if (replacing && apiKey.trim()) patch.apiKey = apiKey.trim()
    setSaving(true)
    try {
      const ok = await onSave(patch)
      if (ok) onOpenChange(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <ConnectorsDialog
      open={open}
      onOpenChange={onOpenChange}
      vendor={connector.vendorKey || connector.type}
      title={`Configure ${connector.name}`}
      description={[connector.environment === "staging" ? "Staging" : "Production", method].join(" · ")}
      footer={
        <>
          <button type="button" className="cno-btn ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </button>
          <button type="button" className="cno-btn dark" disabled={!changed || saving} onClick={() => void save()}>
            {saving ? <Loader2 size={16} className="cno-spin" aria-hidden /> : null}
            {saving ? "Saving" : "Save changes"}
          </button>
        </>
      }
    >
      {isOAuth ? (
        <div className="cno-field">
          Authorization
          <div className="cno-stored">
            <Lock size={15} color={expired ? "#A3333D" : "#0B8A5C"} aria-hidden />
            <span>{expired ? "Expired · sign in again to resume" : "Signed in · tokens are stored encrypted"}</span>
            {onReconnect ? (
              <button type="button" className="cno-btn ghost xs" onClick={onReconnect}>
                Reconnect
              </button>
            ) : null}
          </div>
          <span className="cno-hint">Tokens are never shown. Reconnect signs in again and replaces them.</span>
        </div>
      ) : (
        <label className="cno-field">
          {connector.authType === "webhook" ? "Signing secret" : "API key"}
          {replacing ? (
            <>
              <input
                className="cno-in"
                type="password"
                autoComplete="off"
                autoFocus
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="Paste the new key"
              />
              <span className="cno-hint">Write only. Encrypted on save and never shown again.</span>
            </>
          ) : (
            <>
              <div className="cno-stored">
                <Lock size={15} color={connector.maskedApiKey ? "#0B8A5C" : "#8A8B85"} aria-hidden />
                <span>{connector.maskedApiKey ? `Stored · ${connector.maskedApiKey}` : "Not set"}</span>
                <button type="button" className="cno-btn ghost xs" onClick={() => setReplacing(true)}>
                  {connector.maskedApiKey ? "Replace" : "Add"}
                </button>
              </div>
              <span className="cno-hint">Stored secrets are never shown. Replace writes a new one.</span>
            </>
          )}
        </label>
      )}
      {missingScope ? (
        <div className="cno-field">
          Missing scope
          <div className="cno-note">
            <span style={{ flex: 1 }}>
              A permission an action needs was not granted{missingScopeNote ? `, ${missingScopeNote}` : ""}.
              {isOAuth ? " Reconnect and approve it." : " Update the key's permissions in the vendor."}
            </span>
          </div>
        </div>
      ) : null}
      <label className="cno-field">
        Sync interval
        <select className="cno-in" value={interval} onChange={(event) => setInterval(event.target.value)}>
          {!knownInterval ? <option value={current}>{syncIntervalLabel(current)} (current)</option> : null}
          {SYNC_INTERVALS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <span className="cno-hint">How often Gravitre pulls new content from {connector.type} into Knowledge.</span>
      </label>
    </ConnectorsDialog>
  )
}

/**
 * Remove dialog: the blast radius first (what loses this system, what happens
 * to its data under the org's removal policy), then type the name to confirm.
 * `onRemove` calls POST /api/connectors/{id}/delete with that name.
 */
export function RemoveConnectorDialog({
  connector,
  open,
  onOpenChange,
  onRemove,
  agents,
  workflows,
  plays,
}: {
  connector: DialogConnector
  open: boolean
  onOpenChange: (open: boolean) => void
  onRemove: (confirmName: string) => Promise<boolean>
  agents: number
  workflows: number
  plays: number
}) {
  const [typed, setTyped] = useState("")
  const [removing, setRemoving] = useState(false)
  const { data: removal } = useDataRemoval(open)

  useEffect(() => {
    if (open) setTyped("")
  }, [open])

  const users = usageSentence(agents, workflows)
  const bullets: Array<{ text: string; mute?: boolean }> = []
  if (users) bullets.push({ text: `${users} lose ${connector.type}. Their runs that need it fail until it is connected again.` })
  if (plays) bullets.push({ text: `${plays} ${plays === 1 ? "play reads" : "plays read"} ${connector.type} and will wait on a connector.` })
  const policyLines = disconnectImpactLines(removal?.policy, connector.type, connector.vendorKey || connector.type)
  const records = connector.recordsSynced ?? 0
  for (const line of policyLines) {
    const keepsVendor = line.startsWith("Gravitre's access is not revoked")
    bullets.push({ text: line, mute: keepsVendor })
  }
  if (records > 0) bullets.splice(users ? 1 : 0, 0, { text: `${records.toLocaleString()} synced records came from this connection.` })

  const matches = typed === connector.name
  const remove = async () => {
    if (!matches || removing) return
    setRemoving(true)
    try {
      const ok = await onRemove(typed)
      if (ok) onOpenChange(false)
    } finally {
      setRemoving(false)
    }
  }

  return (
    <ConnectorsAlertDialog
      open={open}
      onOpenChange={onOpenChange}
      icon={<Trash2 size={18} strokeWidth={2} />}
      title={`Remove ${connector.name}?`}
      description="This cannot be undone. Here is what happens right away:"
      footer={
        <>
          <button type="button" className="cno-btn ghost" onClick={() => onOpenChange(false)}>
            Keep connector
          </button>
          <button type="button" className="cno-btn danger" disabled={!matches || removing} onClick={() => void remove()}>
            {removing ? <Loader2 size={16} className="cno-spin" aria-hidden /> : null}
            {removing ? "Removing" : "Remove"}
          </button>
        </>
      }
    >
      <ConnectorsBullets items={bullets} />
      <label className="cno-field">
        <span>
          Type <span className="cno-mono" style={{ color: "inherit", fontWeight: 600 }}>{connector.name}</span> to confirm
        </span>
        <input
          className="cno-in"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void remove()
          }}
          aria-label="Connector name"
          autoComplete="off"
        />
      </label>
    </ConnectorsAlertDialog>
  )
}
