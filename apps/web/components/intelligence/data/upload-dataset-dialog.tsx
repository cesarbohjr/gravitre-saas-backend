"use client"

/** "Upload a file": read a CSV, JSON or document and add it to a new or existing training dataset. */
import { useRef, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { trainingApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { ensureSelectedOrg } from "@/lib/org-context"
import type { TrainingDataset } from "@/types/api"
import { parseUpload, UPLOAD_ACCEPT, type ParsedUpload } from "./parse-upload"

const field =
  "min-h-11 w-full rounded-[var(--g-radius-field)] border border-[color:var(--g-border-default)] bg-background px-3 text-sm outline-none focus:border-[color:var(--g-brand)]"

export function UploadDatasetDialog({
  open,
  onOpenChange,
  datasets,
  onUploaded,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  datasets: TrainingDataset[]
  onUploaded: () => void
}) {
  const [fileName, setFileName] = useState("")
  const [parsed, setParsed] = useState<ParsedUpload | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [destination, setDestination] = useState("new")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lock = useRef(false)

  function reset() {
    setFileName("")
    setParsed(null)
    setParseError(null)
    setName("")
    setDestination("new")
    setError(null)
  }

  async function chooseFile(file: File | undefined) {
    setParsed(null)
    setParseError(null)
    setError(null)
    if (!file) return
    setFileName(file.name)
    setName(file.name.replace(/\.[^.]+$/, ""))
    try {
      setParsed(parseUpload(file.name, await file.text()))
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Could not read this file.")
    }
  }

  const compatible = parsed ? datasets.filter((d) => (parsed.kind === "documents" ? d.type === "documents" : d.type !== "documents")) : []

  async function upload() {
    if (!parsed || lock.current || (destination === "new" && !name.trim())) return
    lock.current = true
    setSaving(true)
    setError(null)
    try {
      if (!(await ensureSelectedOrg(true))) throw new Error("Workspace membership is required to upload data.")
      const datasetId =
        destination === "new"
          ? (await trainingApi.createDataset({ name: name.trim(), type: parsed.kind, description: `Uploaded from ${fileName}` })).id
          : destination
      if (!datasetId) throw new Error("The server did not confirm the new dataset.")
      const result =
        parsed.kind === "documents"
          ? await trainingApi.importDocuments(datasetId, parsed.documents)
          : await trainingApi.uploadRecords(datasetId, parsed.records)
      toast.success(`Added ${result.added} ${parsed.kind === "documents" ? "document" : "example"}${result.added === 1 ? "" : "s"}`)
      onUploaded()
      reset()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload this file. Try again.")
      onUploaded()
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
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload a file</DialogTitle>
          <DialogDescription>
            CSV, JSON or JSONL with input and expected output columns, or a .txt / .md document.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <label className="block space-y-1">
            <span className={TYPE.meta}>File</span>
            <input
              type="file"
              accept={UPLOAD_ACCEPT}
              disabled={saving}
              onChange={(e) => void chooseFile(e.target.files?.[0])}
              className="block min-h-11 w-full text-sm file:mr-3 file:min-h-9 file:rounded-[var(--g-radius-control)] file:border file:border-[color:var(--g-border-default)] file:bg-background file:px-3 file:text-sm"
            />
          </label>
          {parseError ? <p role="alert" className="text-sm text-destructive">{parseError}</p> : null}
          {parsed ? (
            <>
              <p role="status" className={TYPE.bodyMuted}>
                {parsed.kind === "documents"
                  ? "Found 1 document."
                  : `Found ${parsed.records.length} example${parsed.records.length === 1 ? "" : "s"}.`}
              </p>
              <label className="block space-y-1">
                <span className={TYPE.meta}>Add to</span>
                <select className={field} value={destination} disabled={saving} onChange={(e) => setDestination(e.target.value)}>
                  <option value="new">A new dataset</option>
                  {compatible.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </label>
              {destination === "new" ? (
                <label className="block space-y-1">
                  <span className={TYPE.meta}>Dataset name</span>
                  <input className={field} value={name} disabled={saving} onChange={(e) => setName(e.target.value)} />
                </label>
              ) : null}
            </>
          ) : null}
          {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
        </div>
        <DialogFooter>
          <Button variant="outline" className="min-h-11" disabled={saving} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="brand"
            className="min-h-11"
            disabled={!parsed || saving || (destination === "new" && !name.trim())}
            onClick={() => void upload()}
          >
            {saving ? "Uploading…" : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
