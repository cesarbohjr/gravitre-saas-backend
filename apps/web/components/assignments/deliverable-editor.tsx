"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Icon } from "@/lib/icons"
import {
  applyEditableFields,
  parseRawJsonEdit,
  serializeStructuredEdit,
  toEditableFields,
  type EditableField,
  type ParsedDeliverable,
} from "@/lib/assignment-deliverable"

type Mode = "fields" | "raw" | "text"

/** Initial editor state for a deliverable. Pure so it can be unit-tested. */
export function initialEditorState(parsed: ParsedDeliverable): {
  mode: Mode
  fields: EditableField[]
  raw: string
  baseline: string
} {
  if (parsed.format === "text") {
    return { mode: "text", fields: [], raw: parsed.original, baseline: parsed.original.trim() }
  }
  const fields = toEditableFields(parsed.value)
  const baseline = serializeStructuredEdit(parsed.prefix, parsed.value)
  return {
    mode: fields && fields.some((field) => field.kind !== "locked") ? "fields" : "raw",
    fields: fields ?? [],
    raw: parsed.originalJson,
    baseline,
  }
}

/** The exact string sent to `PATCH /agent-jobs/{id}/deliverable`, or an error. */
export function buildEditorContent(
  parsed: ParsedDeliverable,
  mode: Mode,
  fields: EditableField[],
  raw: string,
): { ok: true; content: string } | { ok: false; error: string } {
  if (parsed.format === "text" || mode === "text") {
    const content = raw.trim()
    return content ? { ok: true, content } : { ok: false, error: "The deliverable cannot be empty." }
  }
  if (mode === "raw") {
    const result = parseRawJsonEdit(raw)
    if (!result.ok) return result
    return { ok: true, content: serializeStructuredEdit(parsed.prefix, result.value) }
  }
  const next = applyEditableFields(parsed.value as Record<string, unknown>, fields)
  return { ok: true, content: serializeStructuredEdit(parsed.prefix, next) }
}

export function DeliverableEditorDialog({
  open,
  onOpenChange,
  parsed,
  approved,
  isSaving,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  parsed: ParsedDeliverable
  approved: boolean
  isSaving: boolean
  onSave: (content: string) => Promise<void>
}) {
  const initial = useMemo(() => initialEditorState(parsed), [parsed])
  const [mode, setMode] = useState<Mode>(initial.mode)
  const [fields, setFields] = useState<EditableField[]>(initial.fields)
  const [raw, setRaw] = useState(initial.raw)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const built = buildEditorContent(parsed, mode, fields, raw)
  const unchanged = built.ok && built.content === initial.baseline
  const canToggleRaw = parsed.format === "structured" && initial.fields.some((field) => field.kind !== "locked")

  const switchMode = (next: Mode) => {
    if (next === "raw" && parsed.format === "structured") {
      setRaw(JSON.stringify(applyEditableFields(parsed.value as Record<string, unknown>, fields), null, 2))
    }
    if (next === "fields") {
      const result = parseRawJsonEdit(raw)
      const rebuilt = result.ok ? toEditableFields(result.value) : null
      if (!rebuilt) {
        setSubmitError(result.ok ? "Field editing needs a JSON object at the top level." : result.error)
        return
      }
      setFields(rebuilt)
    }
    setSubmitError(null)
    setMode(next)
  }

  const save = async () => {
    if (!built.ok) {
      setSubmitError(built.error)
      return
    }
    setSubmitError(null)
    try {
      await onSave(built.content)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not save your edits.")
    }
  }

  const updateField = (key: string, text: string) =>
    setFields((current) => current.map((field) => (field.key === key ? { ...field, text } : field)))

  return (
    <Dialog open={open} onOpenChange={(next) => !isSaving && onOpenChange(next)}>
      <DialogContent
        data-dialog="edit-deliverable"
        className="flex max-h-[min(88dvh,820px)] w-[calc(100vw-1.5rem)] max-w-2xl flex-col gap-0 overflow-hidden p-0"
      >
        <DialogHeader className="flex flex-col gap-1 border-b border-[color:var(--g-border-subtle)] px-5 py-4 text-left">
          <DialogTitle>Edit deliverable</DialogTitle>
          <DialogDescription>
            {mode === "fields"
              ? "Edit the wording. Fields that aren't text are kept exactly as the agent returned them."
              : mode === "raw"
                ? "Advanced: edit the underlying JSON. It must stay valid."
                : "Edit the text that will be delivered."}
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-5 py-4">
          {approved ? (
            <p role="note" className="flex items-start gap-2 rounded-[6px] border border-[color:var(--g-approval)]/40 bg-[color:var(--g-approval-soft)] p-3 text-[13px] leading-relaxed text-foreground">
              <Icon name="warning" size="sm" className="mt-0.5 shrink-0 text-[color:var(--g-approval)]" />
              This output is already approved. Saving keeps the approval, and the edited version is what Push delivers.
            </p>
          ) : null}

          {mode === "fields" ? (
            fields.map((field) => {
              const id = `edit-field-${field.key}`
              if (field.kind === "locked") {
                return (
                  <div key={field.key} className="flex flex-col gap-1.5" data-field-kind="locked">
                    <span className="text-[13px] font-medium text-foreground">{field.label}</span>
                    <pre className="max-h-32 overflow-auto whitespace-pre-wrap break-words rounded-[6px] bg-[color:var(--g-surface-1)] p-2 font-mono text-[12px] text-muted-foreground">
                      {field.text || "(empty)"}
                    </pre>
                    <span className="text-[12px] text-muted-foreground">Kept as returned</span>
                  </div>
                )
              }
              return (
                <div key={field.key} className="flex flex-col gap-1.5" data-field-kind={field.kind}>
                  <label htmlFor={id} className="text-[13px] font-medium text-foreground">
                    {field.label}
                  </label>
                  <Textarea
                    id={id}
                    value={field.text}
                    onChange={(event) => updateField(field.key, event.target.value)}
                    className="min-h-20 text-[14px] leading-relaxed"
                    rows={Math.min(10, Math.max(3, field.text.split("\n").length + 1))}
                    aria-describedby={field.kind === "list" ? `${id}-hint` : undefined}
                  />
                  {field.kind === "list" ? (
                    <span id={`${id}-hint`} className="text-[12px] text-muted-foreground">
                      One item per line
                    </span>
                  ) : null}
                </div>
              )
            })
          ) : (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="edit-raw" className="sr-only">
                {mode === "raw" ? "Deliverable JSON" : "Deliverable text"}
              </label>
              <Textarea
                id="edit-raw"
                value={raw}
                onChange={(event) => setRaw(event.target.value)}
                className={mode === "raw" ? "min-h-72 font-mono text-[12px] leading-relaxed" : "min-h-72 text-[14px] leading-relaxed"}
                spellCheck={mode !== "raw"}
              />
            </div>
          )}

          {submitError ? (
            <p role="alert" className="text-[13px] text-destructive">
              {submitError}
            </p>
          ) : null}
        </div>

        <DialogFooter className="flex flex-col-reverse gap-2 border-t border-[color:var(--g-border-subtle)] px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
          {canToggleRaw ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => switchMode(mode === "raw" ? "fields" : "raw")}
              disabled={isSaving}
            >
              {mode === "raw" ? "Back to fields" : "Edit raw JSON"}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button type="button" variant="outline" className="min-h-11 md:min-h-9" onClick={() => onOpenChange(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button type="button" className="min-h-11 md:min-h-9" onClick={() => void save()} disabled={isSaving || unchanged}>
              {isSaving ? "Saving…" : unchanged ? "No changes" : "Save changes"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
