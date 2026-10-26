"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Check, Copy, Info, KeyRound, Loader2, Plus, RefreshCw, Trash2, TriangleAlert } from "lucide-react"
import { toast } from "@/components/agents/overlays/toast"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  API_KEYS_KEY,
  API_KEY_EXPIRIES,
  API_KEY_SCOPES,
  API_REFERENCE_HREF,
  apiKeysApi,
  expiryLabel,
  maskKey,
  scopeLabel,
  visibleKeys,
  type ApiKeyExpiry,
  type ApiKeyScope,
  type WorkspaceApiKey,
} from "@/lib/settings-api/api-keys"
import { SetArt, SetError, SetHeader, SetNote, SetSkeleton, formatDay } from "./settings-kit"
import "./apikeys-settings.css"

type Pending = { kind: "revoke" | "rotate"; key: WorkspaceApiKey } | null

/**
 * Settings > Workspace > API keys (design p10). Owners and admins create,
 * rotate and revoke keys through /api/settings/api-keys; the secret is shown
 * once, right after it is made.
 */
export function ApiKeysSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(isAdmin ? API_KEYS_KEY : null, () => apiKeysApi.list(), {
    revalidateOnFocus: false,
  })
  const [draft, setDraft] = useState("")
  const [scope, setScope] = useState<ApiKeyScope>("read")
  const [expires, setExpires] = useState<ApiKeyExpiry>("90d")
  const [creating, setCreating] = useState(false)
  const [revealed, setRevealed] = useState<{ id: string; name: string; secret: string } | null>(null)
  const [copied, setCopied] = useState(false)
  const [pending, setPending] = useState<Pending>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const header = (
    <SetHeader
      crumb="Settings / Workspace"
      title="API keys"
      description="Keys let your own systems call Gravitre. Each key only sees what its scope allows."
    />
  )

  if (!isAdmin) {
    return (
      <>
        {header}
        <SetNote>Owner or admin permission is required to manage API keys.</SetNote>
      </>
    )
  }

  const keys = visibleKeys(data?.apiKeys)
  const activeCount = keys.filter((key) => !key.expired).length

  const handleCreate = async () => {
    const name = draft.trim()
    if (!name || creating) return
    setCreating(true)
    try {
      const created = await apiKeysApi.create({ name, scope, expires_in: expires })
      if (created.apiKey.key) setRevealed({ id: created.apiKey.id, name: created.apiKey.name, secret: created.apiKey.key })
      setCopied(false)
      setDraft("")
      toast.success("API key created. Copy it now.")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create the API key")
    } finally {
      setCreating(false)
    }
  }

  const handleCopy = async () => {
    if (!revealed) return
    try {
      await navigator.clipboard.writeText(revealed.secret)
      setCopied(true)
    } catch {
      toast.error("Could not copy the key")
    }
  }

  const confirmPending = async () => {
    if (!pending) return
    const { kind, key } = pending
    setPending(null)
    setBusyId(key.id)
    try {
      if (kind === "revoke") {
        await apiKeysApi.revoke(key.id)
        if (revealed?.id === key.id) setRevealed(null)
        toast.success(`${key.name} revoked`)
      } else {
        const rotated = await apiKeysApi.rotate(key.id)
        if (rotated.apiKey.key) setRevealed({ id: key.id, name: key.name, secret: rotated.apiKey.key })
        setCopied(false)
        toast.success(`${key.name} rotated. Copy the new key now.`)
      }
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : kind === "revoke" ? "Could not revoke the key" : "Could not rotate the key")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <>
      {header}

      <SetNote tone="amber" icon={TriangleAlert}>
        The Gravitre API does not accept these keys for sign in yet. Keys you create keep their scope and expiry, and
        start working when key sign in ships.
      </SetNote>

      <section className="gs-card apikeys-create" aria-label="Create an API key">
        <form
          className="apikeys-form"
          onSubmit={(event) => {
            event.preventDefault()
            void handleCreate()
          }}
        >
          <label className="gs-field name">
            Key name
            <input
              placeholder="For example, Data warehouse sync"
              value={draft}
              maxLength={120}
              onChange={(event) => setDraft(event.target.value)}
            />
          </label>
          <label className="gs-field scope">
            Scope
            <select value={scope} onChange={(event) => setScope(event.target.value as ApiKeyScope)}>
              {API_KEY_SCOPES.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="gs-field exp">
            Expires
            <select value={expires} onChange={(event) => setExpires(event.target.value as ApiKeyExpiry)}>
              {API_KEY_EXPIRIES.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="gs-btn dark" disabled={!draft.trim() || creating}>
            {creating ? <Loader2 size={16} className="animate-spin motion-reduce:animate-none" aria-hidden /> : <Plus size={16} aria-hidden />}
            Create key
          </button>
        </form>
        {revealed ? (
          <SetNote tone="green" icon={KeyRound} className="apikeys-reveal">
            <div className="row" role="status">
              <div>
                <strong>Copy your key now.</strong> For your safety you will not see it again.
                <div className="gs-mono apikeys-secret" aria-label={`New key for ${revealed.name}`}>
                  {revealed.secret}
                </div>
              </div>
              <button type="button" className="gs-btn line sm" onClick={() => void handleCopy()}>
                {copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </SetNote>
        ) : null}
      </section>

      <section className="gs-card clip" aria-label="Your keys">
        <div className="gs-card-head">
          <h3>Your keys</h3>
          {data ? <span className="gs-count">{activeCount} active</span> : null}
        </div>
        {isLoading && !data ? (
          <SetSkeleton rows={3} label="Loading API keys" />
        ) : error ? (
          <SetError message="Could not load API keys." onRetry={() => void mutate()} />
        ) : keys.length === 0 ? (
          <div className="apikeys-empty">
            <SetArt name="settings-api-keys" ratio="320 / 200" />
            <div>
              <h4>No API keys yet</h4>
              <p>
                Create a key above to connect a warehouse, a script or your own app. Start with read only and widen the
                scope later.
              </p>
              <Link href={API_REFERENCE_HREF} className="gs-link">
                API reference
              </Link>
            </div>
          </div>
        ) : (
          <div className="gs-tbl stack apikeys-tbl" role="table" aria-label="API keys">
            <div className="gs-tr head" role="row">
              <div className="gs-th" role="columnheader">
                Name
              </div>
              <div className="gs-th" role="columnheader">
                Scope
              </div>
              <div className="gs-th" role="columnheader">
                Created
              </div>
              <div className="gs-th" role="columnheader">
                Expires
              </div>
              <div className="gs-th" role="columnheader">
                <span className="sr-only">Actions</span>
              </div>
            </div>
            {keys.map((key) => (
              <div key={key.id} className="gs-row" role="row">
                <div className="gs-td" role="cell">
                  <div className="t">{key.name}</div>
                  <div className="s gs-mono">{maskKey(key)}</div>
                </div>
                <div className="gs-td" role="cell">
                  <span className="gs-chip">{scopeLabel(key.scope)}</span>
                </div>
                <div className="gs-td gs-mono date" role="cell">
                  {formatDay(key.created_at) ?? "Not recorded"}
                </div>
                <div className={`gs-td date${key.expired ? " expired" : ""}`} role="cell">
                  {expiryLabel(key)}
                </div>
                <div className="gs-td actions" role="cell">
                  <button
                    type="button"
                    className="gs-iconbtn"
                    aria-label={`Rotate ${key.name}`}
                    title="Rotate"
                    disabled={busyId === key.id || key.expired}
                    onClick={() => setPending({ kind: "rotate", key })}
                  >
                    <RefreshCw size={16} aria-hidden />
                  </button>
                  <button
                    type="button"
                    className="gs-iconbtn danger"
                    aria-label={`Revoke ${key.name}`}
                    title="Revoke"
                    disabled={busyId === key.id}
                    onClick={() => setPending({ kind: "revoke", key })}
                  >
                    {busyId === key.id ? (
                      <Loader2 size={16} className="animate-spin motion-reduce:animate-none" aria-hidden />
                    ) : (
                      <Trash2 size={16} aria-hidden />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <SetNote icon={Info}>
        Keys act as this workspace. Anything a key writes goes through the same approvals and shows in the{" "}
        <Link href="/audit">Audit trail</Link>.
      </SetNote>

      <AlertDialog open={pending !== null} onOpenChange={(open) => (open ? null : setPending(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pending?.kind === "rotate" ? `Rotate ${pending.key.name}?` : `Revoke ${pending?.key.name ?? "this key"}?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pending?.kind === "rotate"
                ? "The current key stops working right away. You get a new key to copy, with the same scope and expiry."
                : "Anything using this key stops working right away. This cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void confirmPending()}>
              {pending?.kind === "rotate" ? "Rotate key" : "Revoke key"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
