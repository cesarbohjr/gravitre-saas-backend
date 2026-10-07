"use client"

/**
 * "Use for…": save a public dataset for any purpose (evaluation, RAG,
 * benchmarking…) on an existing model, agent, department or workflow. Uses the
 * same reference endpoint as "Import to train"; only metadata is stored.
 */
import { useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  EXTERNAL_DATASET_PURPOSES,
  type ExternalDatasetPurpose,
} from "@/components/intelligence/external-datasets-section"
import { trainingApi, workflowsApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import type { DataSources } from "./use-data-sources"

type UseForTarget = "model" | "agent" | "department" | "workflow"

const TARGET_TYPES: Array<{ value: UseForTarget; label: string }> = [
  { value: "model", label: "Model" },
  { value: "agent", label: "Agent" },
  { value: "department", label: "Department" },
  { value: "workflow", label: "Workflow" },
]

const field =
  "min-h-11 w-full rounded-[var(--g-radius-field)] border border-[color:var(--g-border-default)] bg-background px-3 text-sm outline-none focus:border-[color:var(--g-brand)]"

export function UseForDialog({
  open,
  onOpenChange,
  providerId,
  datasetId,
  sources,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  providerId: string
  datasetId: string
  sources: DataSources
}) {
  const [purpose, setPurpose] = useState<ExternalDatasetPurpose>("evaluation")
  const [targetType, setTargetType] = useState<UseForTarget>("agent")
  const [targetId, setTargetId] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const lock = useRef(false)

  const workflows = useSWR(
    open && targetType === "workflow" ? "external-dataset-target-workflows" : null,
    () => workflowsApi.list(),
    { revalidateOnFocus: false },
  )

  const options = useMemo(() => {
    if (targetType === "model") return (sources.mlModels.data?.models ?? []).map((m) => ({ id: m.id, label: m.name || "Untitled model" }))
    if (targetType === "agent") return (sources.agents.data?.agents ?? []).map((a) => ({ id: String(a.id), label: a.name || a.role || "Untitled agent" }))
    if (targetType === "workflow") return (workflows.data?.workflows ?? []).map((w) => ({ id: w.id, label: w.name || "Untitled workflow" }))
    const departments = new Set((sources.agents.data?.agents ?? []).map((a) => String(a.department || "").trim()).filter(Boolean))
    return Array.from(departments).sort().map((d) => ({ id: d, label: d.charAt(0).toUpperCase() + d.slice(1) }))
  }, [targetType, sources.mlModels.data, sources.agents.data, workflows.data])

  const loading =
    targetType === "model" ? sources.mlModels.isLoading : targetType === "workflow" ? workflows.isLoading : sources.agents.isLoading
  const loadError =
    targetType === "model" ? sources.mlModels.error : targetType === "workflow" ? workflows.error : sources.agents.error
  const ready = options.some((o) => o.id === targetId)

  async function save() {
    if (lock.current || !ready) return
    lock.current = true
    setSaving(true)
    setError(null)
    setSaved(null)
    try {
      const result = await trainingApi.createExternalDatasetReference({
        provider: providerId,
        datasetId,
        purpose,
        targetType,
        targetId,
        accessMode: "reference",
        metadata: { source: "intelligence_data" },
      })
      if (!result.id) throw new Error("The server did not confirm the save. Your choices are kept.")
      const label = options.find((o) => o.id === targetId)?.label ?? "the selected target"
      const purposeLabel = EXTERNAL_DATASET_PURPOSES.find((p) => p.value === purpose)?.label ?? purpose
      setSaved(`Saved for ${label} (${purposeLabel.toLowerCase()}). Only metadata is stored; no files were downloaded.`)
      void sources.references.mutate()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this dataset.")
    } finally {
      lock.current = false
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (lock.current) return
        onOpenChange(next)
        if (!next) {
          setSaved(null)
          setError(null)
        }
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Use this dataset for…</DialogTitle>
          <DialogDescription className="break-all">{datasetId}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <label className="block space-y-1">
            <span className={TYPE.meta}>Purpose</span>
            <select className={field} value={purpose} disabled={saving} onChange={(e) => { setPurpose(e.target.value as ExternalDatasetPurpose); setSaved(null) }}>
              {EXTERNAL_DATASET_PURPOSES.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className={TYPE.meta}>Use with</span>
            <select
              className={field}
              value={targetType}
              disabled={saving}
              onChange={(e) => { setTargetType(e.target.value as UseForTarget); setTargetId(""); setSaved(null) }}
            >
              {TARGET_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className={TYPE.meta}>Which {targetType}</span>
            <select
              className={field}
              value={targetId}
              disabled={saving || loading || Boolean(loadError)}
              onChange={(e) => { setTargetId(e.target.value); setSaved(null) }}
            >
              <option value="">
                {loading ? "Loading…" : loadError ? "Couldn't load the list" : options.length === 0 ? `No ${targetType}s yet` : `Choose a ${targetType}`}
              </option>
              {options.map((o) => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </label>
          {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
          {saved ? <p role="status" className="text-sm text-[color:var(--g-brand-active)]">{saved}</p> : null}
        </div>
        <DialogFooter>
          <Button variant="outline" className="min-h-11" disabled={saving} onClick={() => onOpenChange(false)}>
            {saved ? "Done" : "Cancel"}
          </Button>
          <Button variant="brand" className="min-h-11" disabled={!ready || saving} onClick={() => void save()}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
