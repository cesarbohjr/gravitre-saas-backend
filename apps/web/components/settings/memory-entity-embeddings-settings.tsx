"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Brain, Check, Info } from "lucide-react"
import { connectorsApi, settingsApi } from "@/lib/api"
import {
  CONNECTORS_KEY,
  MEMORY_KEY,
  appChips,
  samePolicy,
  scopeText,
  type MemoryPolicy,
} from "@/lib/settings-api/ai-models"
import { SetError, SetIco, SetNote, SetSkeleton, SetSwitch } from "./settings-kit"
import { SettingsSaveBar } from "./settings-save-bar"

/**
 * Chat entity matching (Memory), STA-316: org opt-in for opaque-token entity
 * embeddings, optionally limited to some connected apps. Saved through
 * PUT /api/settings/memory-entity-embeddings (owners and admins only).
 */
export function MemoryEntityEmbeddingsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(MEMORY_KEY, () => settingsApi.getMemoryEntityEmbeddings(), {
    revalidateOnFocus: false,
  })
  const connectors = useSWR(CONNECTORS_KEY, () => connectorsApi.list(), { revalidateOnFocus: false })
  const remote = data?.memoryEntityEmbeddings
  const baseline = useMemo<MemoryPolicy>(
    () => ({
      enabled: Boolean(remote?.enabled),
      connectors: Array.isArray(remote?.connectors) ? remote.connectors.map((id) => String(id).toLowerCase()) : [],
    }),
    [remote],
  )
  const [draft, setDraft] = useState<MemoryPolicy>(baseline)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  useEffect(() => setDraft(baseline), [baseline])

  const chips = useMemo(() => appChips(connectors.data?.connectors, baseline.connectors), [connectors.data, baseline.connectors])
  const dirty = Boolean(remote) && !samePolicy(draft, baseline)

  const toggleApp = (id: string) => {
    setDraft((prev) => ({
      ...prev,
      connectors: prev.connectors.includes(id) ? prev.connectors.filter((item) => item !== id) : [...prev.connectors, id],
    }))
    setSaveError(null)
  }

  const save = async () => {
    if (!isAdmin) return
    setSaving(true)
    setSaveError(null)
    try {
      const payload = { enabled: draft.enabled, connectors: draft.enabled ? draft.connectors : [] }
      const result = await settingsApi.updateMemoryEntityEmbeddings(payload)
      const saved = result?.memoryEntityEmbeddings
      await mutate(saved ? { memoryEntityEmbeddings: saved } : undefined, { revalidate: !saved })
      setSavedAt(Date.now())
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save the Memory setting")
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="gs-card clip" aria-label="Chat entity matching (Memory)">
      <div className="gs-row-sec">
        <SetIco icon={Brain} />
        <div className="gs-what">
          <b>Chat entity matching (Memory)</b>
          <span>
            Better matching when you mention people or channels loosely, like &ldquo;Sarah&rdquo; or &ldquo;#sales&rdquo;.
            Off by default.
          </span>
        </div>
        {remote ? (
          <SetSwitch
            label="Enable entity matching"
            checked={draft.enabled}
            disabled={!isAdmin || saving}
            onChange={(next) => {
              setDraft((prev) => ({ ...prev, enabled: next }))
              setSaveError(null)
            }}
          />
        ) : null}
      </div>
      <div className="aimodels-memory-body">
        <SetNote icon={Info}>
          <div>
            When this is on, Gravitre sends <strong>opaque tokens</strong> (HMAC digests) and redacted fragments to an
            embedding provider (OpenAI) to match known names. Raw emails, assignee names and channel names are never sent.
          </div>
          <div style={{ marginTop: 6 }}>
            Exact alias matches stay on your local cache. Vectors are stored apart from the knowledge base and expire after
            30 days.
          </div>
        </SetNote>

        {isLoading && !remote ? (
          <SetSkeleton rows={2} label="Loading Memory settings" />
        ) : error || !remote ? (
          <SetError message="Could not load the Memory setting." onRetry={() => void mutate()} />
        ) : draft.enabled ? (
          <div>
            <div className="aimodels-apps-label">
              Limit to these apps <span>(leave all off to apply everywhere)</span>
            </div>
            {connectors.isLoading && !connectors.data ? (
              <SetSkeleton rows={1} label="Loading connected apps" />
            ) : connectors.error ? (
              <SetError message="Could not load your connected apps." onRetry={() => void connectors.mutate()} />
            ) : chips.length === 0 ? (
              <p className="aimodels-scope">
                No apps connected yet. <Link href="/connectors">Connect an app</Link> to limit matching to it.
              </p>
            ) : (
              <div className="aimodels-apps" role="group" aria-label="Limit to these apps">
                {chips.map((chip) => {
                  const on = draft.connectors.includes(chip.id)
                  return (
                    <button
                      key={chip.id}
                      type="button"
                      className="gs-leg"
                      aria-pressed={on}
                      disabled={!isAdmin || saving}
                      title={chip.stale ? "No longer connected" : undefined}
                      onClick={() => toggleApp(chip.id)}
                    >
                      {on ? <Check size={14} aria-hidden /> : null}
                      {chip.name}
                      {chip.stale ? <span className="sr-only"> (no longer connected)</span> : null}
                    </button>
                  )
                })}
              </div>
            )}
            <div className="aimodels-scope">{scopeText(chips, draft.connectors)}</div>
          </div>
        ) : null}

        {!isAdmin ? <p className="aimodels-scope">Only owners and admins can change this setting.</p> : null}
        {saveError ? (
          <p role="alert" className="gs-note red">
            {saveError}
          </p>
        ) : null}
      </div>
      {isAdmin ? (
        <SettingsSaveBar
          dirty={dirty}
          saving={saving}
          savedAt={savedAt}
          onDiscard={() => {
            setDraft(baseline)
            setSaveError(null)
          }}
          onSave={() => void save()}
        />
      ) : null}
    </section>
  )
}
