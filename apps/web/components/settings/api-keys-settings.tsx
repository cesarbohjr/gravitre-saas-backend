"use client"

import { useState } from "react"
import useSWR from "swr"
import { Check, Copy, Eye, EyeOff, Key, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { settingsApi } from "@/lib/api"
import type { ApiKey } from "@/types/api"

export function ApiKeysSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(isAdmin ? "/api/settings/api-keys" : null, () => settingsApi.listApiKeys(), { revalidateOnFocus: false })
  const [showKeyId, setShowKeyId] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [newName, setNewName] = useState("")
  const [revealedKey, setRevealedKey] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const apiKeys = data?.apiKeys ?? []

  const handleCopy = async (key: ApiKey) => {
    const value = (showKeyId === key.id && key.key) || revealedKey && key.id === showKeyId ? (key.key || revealedKey) : key.key_prefix
    try {
      await navigator.clipboard.writeText(value || key.key_prefix)
      setCopiedId(key.id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      toast.error("Could not copy key")
    }
  }

  const handleCreateKey = async () => {
    if (!isAdmin) return
    setIsCreating(true)
    try {
      const created = await settingsApi.createApiKey(newName.trim() || "API key")
      setRevealedKey(created.apiKey.key ?? null)
      setShowKeyId(created.apiKey.id)
      setNewName("")
      toast.success("API key created. Copy it now if the full value is shown.")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create API key")
    } finally {
      setIsCreating(false)
    }
  }

  const handleRotateKey = async (keyId: string) => {
    if (!confirm("Rotating this key will invalidate the old key immediately. Continue?")) return
    setBusyId(keyId)
    try {
      const rotated = await settingsApi.rotateApiKey(keyId)
      setRevealedKey(rotated.apiKey.key ?? null)
      setShowKeyId(rotated.apiKey.id)
      toast.success("API key rotated")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to rotate key")
    } finally {
      setBusyId(null)
    }
  }

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm("Revoke this API key? Existing clients will stop authenticating.")) return
    setBusyId(keyId)
    try {
      await settingsApi.revokeApiKey(keyId)
      toast.success("API key revoked")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke key")
    } finally {
      setBusyId(null)
    }
  }

  if (!isAdmin) {
    return <p className="text-sm text-muted-foreground">Admin or owner permission is required to manage API keys.</p>
  }
  if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading API keys…</p>
  if (error) {
    return (
      <div role="alert" className="space-y-3">
        <p className="text-sm">Could not load API keys.</p>
        <Button variant="outline" className="min-h-11" onClick={() => void mutate()}>Retry API keys</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6" aria-label="API keys">
      {apiKeys.length === 0 ? <p className="text-sm text-muted-foreground">No API keys have been created for this organization.</p> : null}
      {apiKeys.map((apiKey) => {
        const full = (showKeyId === apiKey.id && (apiKey.key || (revealedKey && showKeyId === apiKey.id))) ? (apiKey.key || revealedKey) : null
        return (
          <div key={apiKey.id} className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="break-words text-sm font-medium">{apiKey.name}</p>
                <p className="text-xs capitalize text-muted-foreground">{apiKey.status} · created {apiKey.created_at ? new Date(apiKey.created_at).toLocaleDateString() : "recently"}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" className="min-h-11" onClick={() => setShowKeyId(showKeyId === apiKey.id ? null : apiKey.id)}>
                  {showKeyId === apiKey.id ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
                <Button variant="outline" className="min-h-11" onClick={() => void handleCopy(apiKey)}>
                  {copiedId === apiKey.id ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
                <Button variant="outline" className="min-h-11" disabled={busyId === apiKey.id || apiKey.status === "revoked"} onClick={() => void handleRotateKey(apiKey.id)}>
                  {busyId === apiKey.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Rotate
                </Button>
                <Button variant="ghost" className="min-h-11 text-destructive" disabled={busyId === apiKey.id || apiKey.status === "revoked"} onClick={() => void handleRevokeKey(apiKey.id)}>Revoke</Button>
              </div>
            </div>
            <code className="mt-3 block break-all rounded bg-secondary px-3 py-2 text-xs">
              {full ?? `${apiKey.key_prefix}••••••••`}
            </code>
          </div>
        )
      })}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input aria-label="New API key name" value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Key name" className="min-h-11" />
        <Button className="min-h-11 gap-2" disabled={isCreating} onClick={() => void handleCreateKey()}>
          {isCreating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Key className="h-3.5 w-3.5" />}
          Create key
        </Button>
      </div>
    </div>
  )
}
