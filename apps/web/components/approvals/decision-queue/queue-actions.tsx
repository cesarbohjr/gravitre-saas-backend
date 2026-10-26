"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { approvalsApi } from "@/lib/api"
import { humanize, type Approval } from "./model"

type FieldKind = "text" | "number" | "boolean" | "json"

function kindOf(value: unknown): FieldKind {
  if (typeof value === "number") return "number"
  if (typeof value === "boolean") return "boolean"
  if (typeof value === "string" || value === null || value === undefined) return "text"
  return "json"
}

function draftOf(value: unknown, kind: FieldKind): string {
  if (kind === "json") return JSON.stringify(value, null, 2)
  if (kind === "boolean") return value ? "true" : "false"
  return value == null ? "" : String(value)
}

/**
 * "Edit, then approve": change the values the agent will send, then approve the edited
 * version. The backend rewrites the stored arguments and re-binds them, so approval runs
 * exactly what is shown here.
 */
export function EditApproveDialog({
  approval,
  open,
  busy,
  onOpenChange,
  onSubmit,
}: {
  approval: Approval
  open: boolean
  busy: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (parameters: Record<string, unknown>) => void
}) {
  const source = useMemo(() => approval.editableParameters ?? {}, [approval.editableParameters])
  const fields = useMemo(
    () => Object.entries(source).map(([key, value]) => ({ key, kind: kindOf(value), original: value })),
    [source],
  )
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setDrafts(Object.fromEntries(fields.map((f) => [f.key, draftOf(f.original, f.kind)])))
    setError(null)
  }, [open, fields])

  const submit = () => {
    const out: Record<string, unknown> = {}
    for (const f of fields) {
      const raw = drafts[f.key] ?? ""
      if (f.kind === "number") {
        const n = Number(raw)
        if (raw.trim() === "" || !Number.isFinite(n)) {
          setError(`${humanize(f.key)} needs a number`)
          return
        }
        out[f.key] = n
      } else if (f.kind === "boolean") {
        out[f.key] = raw === "true"
      } else if (f.kind === "json") {
        try {
          out[f.key] = JSON.parse(raw)
        } catch {
          setError(`${humanize(f.key)} is not valid JSON`)
          return
        }
      } else {
        out[f.key] = f.original === null && raw === "" ? null : raw
      }
    }
    setError(null)
    onSubmit(out)
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Edit, then approve</DialogTitle>
          <DialogDescription>
            Change what {approval.title} will send. Approving runs the edited version, and the original stays on the
            record.
          </DialogDescription>
        </DialogHeader>
        <div className="dq-edit-fields">
          {fields.map((f) => {
            const id = `dq-edit-${f.key}`
            return (
              <label key={f.key} className="dq-edit-field" htmlFor={id}>
                <span>{humanize(f.key)}</span>
                {f.kind === "boolean" ? (
                  <select
                    id={id}
                    value={drafts[f.key] ?? "false"}
                    onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))}
                  >
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                ) : f.kind === "json" ? (
                  <Textarea
                    id={id}
                    className="font-mono text-[13px]"
                    rows={Math.min(10, Math.max(3, (drafts[f.key] ?? "").split("\n").length))}
                    value={drafts[f.key] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))}
                  />
                ) : (
                  <input
                    id={id}
                    type={f.kind === "number" ? "number" : "text"}
                    value={drafts[f.key] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))}
                  />
                )}
              </label>
            )
          })}
        </div>
        {error ? (
          <p className="dq-edit-error" role="alert">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <button type="button" className="ag-btn ghost" disabled={busy} onClick={() => onOpenChange(false)}>
            Cancel
          </button>
          <button type="button" className="ag-btn primary" disabled={busy} onClick={submit}>
            {busy ? "Saving..." : "Save and approve"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Hand a request to a teammate whose role can approve writes. */
export function DelegateDialog({
  approval,
  open,
  busy,
  onOpenChange,
  onSubmit,
}: {
  approval: Approval
  open: boolean
  busy: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (userId: string, note: string) => void
}) {
  const { data, error, isLoading } = useSWR(open ? "/api/approvals/delegates" : null, () => approvalsApi.delegates())
  const people = data?.delegates ?? []
  const [userId, setUserId] = useState("")
  const [note, setNote] = useState("")

  useEffect(() => {
    if (!open) return
    setUserId(approval.delegatedToId ?? "")
    setNote("")
  }, [open, approval.delegatedToId])

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>Hand to a teammate</DialogTitle>
          <DialogDescription>They get a notification and the request shows as theirs in the queue.</DialogDescription>
        </DialogHeader>
        <div className="dq-edit-fields">
          <label className="dq-edit-field" htmlFor="dq-delegate-to">
            <span>Teammate</span>
            <select
              id="dq-delegate-to"
              value={userId}
              disabled={isLoading || people.length === 0}
              onChange={(e) => setUserId(e.target.value)}
            >
              <option value="">
                {isLoading ? "Loading..." : people.length ? "Pick someone" : "No one else can approve writes"}
              </option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.role ? ` · ${p.role}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="dq-edit-field" htmlFor="dq-delegate-note">
            <span>Note (optional)</span>
            <Textarea
              id="dq-delegate-note"
              rows={3}
              maxLength={500}
              placeholder="For example: you own the MSP list"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
        </div>
        {error ? (
          <p className="dq-edit-error" role="alert">
            Could not load teammates.
          </p>
        ) : null}
        <DialogFooter>
          <button type="button" className="ag-btn ghost" disabled={busy} onClick={() => onOpenChange(false)}>
            Cancel
          </button>
          <button
            type="button"
            className="ag-btn primary"
            disabled={busy || !userId}
            onClick={() => onSubmit(userId, note.trim())}
          >
            {busy ? "Handing off..." : "Hand off"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
