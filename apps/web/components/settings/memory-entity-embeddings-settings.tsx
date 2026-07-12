"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Info, Loader2, Save, Shield, Check } from "lucide-react"
import { settingsApi } from "@/lib/api"
import { toast } from "sonner"

const CONNECTOR_OPTIONS = [
  { id: "asana", label: "Asana" },
  { id: "slack", label: "Slack" },
  { id: "hubspot", label: "HubSpot" },
  { id: "jira", label: "Jira" },
  { id: "apollo", label: "Apollo" },
] as const

type MemoryEntityEmbeddingsPolicy = {
  enabled: boolean
  connectors: string[]
}

export function MemoryEntityEmbeddingsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, mutate, isLoading } = useSWR(
    "/api/settings/memory-entity-embeddings",
    () => settingsApi.getMemoryEntityEmbeddings(),
    { revalidateOnFocus: false },
  )
  const remote = data?.memoryEntityEmbeddings
  const [enabled, setEnabled] = useState(false)
  const [connectors, setConnectors] = useState<string[]>([])
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!remote) return
    setEnabled(Boolean(remote.enabled))
    setConnectors(Array.isArray(remote.connectors) ? remote.connectors.map(String) : [])
  }, [remote])

  const dirty = useMemo(() => {
    if (!remote) return false
    const remoteConnectors = [...(remote.connectors || [])].map(String).sort()
    const localConnectors = [...connectors].sort()
    return (
      Boolean(remote.enabled) !== enabled ||
      JSON.stringify(remoteConnectors) !== JSON.stringify(localConnectors)
    )
  }, [remote, enabled, connectors])

  const toggleConnector = (id: string) => {
    setConnectors((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    )
  }

  const handleSave = async () => {
    if (!isAdmin) {
      toast.error("Only organization admins can change this setting")
      return
    }
    setIsSaving(true)
    try {
      const payload: MemoryEntityEmbeddingsPolicy = {
        enabled,
        connectors: enabled ? connectors : [],
      }
      await settingsApi.updateMemoryEntityEmbeddings(payload)
      await mutate()
      setSaved(true)
      toast.success(enabled ? "Chat entity matching enabled" : "Chat entity matching disabled")
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error("[settings] memory entity embeddings save failed:", err)
      toast.error("Failed to save Memory entity matching setting")
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading && !remote) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading Memory settings…
      </div>
    )
  }

  return (
    <div className="space-y-4 pt-6 border-t border-border">
      <div>
        <h3 className="text-sm font-medium text-foreground">Chat entity matching (Memory)</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Improve chat matching of people and channels when you use fuzzy mentions (for example
          “Sarah” or “#sales”). Off by default.
        </p>
      </div>

      <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/40 border border-border">
        <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
        <div className="text-xs text-muted-foreground space-y-1.5">
          <p>
            When enabled, Gravitre may send <span className="text-foreground font-medium">non-raw opaque tokens</span>{" "}
            (HMAC digests) and redacted mention fragments to a third-party embedding API (OpenAI) to
            match known entities. Raw emails, assignee names, and channel names are never embedded.
          </p>
          <p>
            Exact alias matches still use your local entity cache without a provider call. This setting
            does <span className="text-foreground font-medium">not</span> mean “no data leaves Gravitre”
            while Memory matching is on.
          </p>
          <p>Vectors are stored separately from the knowledge base and expire after 30 days.</p>
        </div>
      </div>

      <label
        className={`flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/30 transition-colors ${
          isAdmin ? "cursor-pointer hover:bg-secondary/50" : "opacity-70"
        }`}
      >
        <div className="flex items-center gap-3">
          <Shield className="h-4 w-4 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">Enable opaque-token entity matching</p>
            <p className="text-xs text-muted-foreground">
              Opt in for Memory Phase 1 embeddings behind sensitive chat fields
            </p>
          </div>
        </div>
        <input
          type="checkbox"
          className="rounded border-border"
          checked={enabled}
          disabled={!isAdmin || isSaving}
          onChange={(e) => setEnabled(e.target.checked)}
        />
      </label>

      {enabled ? (
        <div className="space-y-2 pl-1">
          <p className="text-xs text-muted-foreground">
            Optional connector allowlist — leave all unchecked to apply to every connected app when
            enabled.
          </p>
          <div className="flex flex-wrap gap-2">
            {CONNECTOR_OPTIONS.map((connector) => {
              const active = connectors.includes(connector.id)
              return (
                <button
                  key={connector.id}
                  type="button"
                  disabled={!isAdmin || isSaving}
                  onClick={() => toggleConnector(connector.id)}
                  className={`px-2.5 py-1 rounded-md text-xs border transition-colors ${
                    active
                      ? "border-foreground/30 bg-foreground/5 text-foreground"
                      : "border-border text-muted-foreground hover:bg-secondary/40"
                  }`}
                >
                  {connector.label}
                </button>
              )
            })}
          </div>
        </div>
      ) : null}

      {!isAdmin ? (
        <p className="text-xs text-muted-foreground">Only organization admins can change this setting.</p>
      ) : (
        <Button size="sm" className="gap-2" onClick={handleSave} disabled={isSaving || !dirty}>
          {isSaving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : saved ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          {saved ? "Saved" : "Save Memory setting"}
        </Button>
      )}
    </div>
  )
}
