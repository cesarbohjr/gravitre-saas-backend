import { useEffect, useRef, useState } from "react"
import { AlertTriangle, ArrowUpRight, Check, ShieldCheck } from "lucide-react"

import { ConnectorIcon, connectorLabel } from "@/components/connector-icon"
import { Button, SectionLabel } from "@/components/ui"
import { cn } from "@/lib/cn"
import { connectorOf, flattenParams, humanizeKey, isDestructiveAction } from "@/lib/params"
import type { Suggestion } from "@/lib/types"

/**
 * The write-approval gate (Part C).
 *
 * The rule this screen exists to satisfy: a user must be able to see exactly
 * what will be written, to which system, with which values, *before* they
 * approve. The previous version asked "Approve hubspot.contacts.create?" and
 * showed none of the staged data, which is not consent — it's a dare.
 *
 * The params rendered here are the ones the *server* echoed back when it staged
 * the write, not the ones we guessed locally, so what you read is what will run.
 */
export function ApprovalPanel({
  suggestion,
  params,
  busy,
  error,
  onApprove,
  onCancel,
}: {
  suggestion: Suggestion
  params: Record<string, unknown>
  busy: boolean
  error?: string
  /** `extra` carries operator-supplied values that force a re-stage. */
  onApprove: (extra?: Record<string, unknown>) => void
  onCancel: () => void
}) {
  const connector = connectorOf(suggestion.invokeAction)
  const destructive = isDestructiveAction(suggestion.invokeAction)

  // Some actions cannot be staged from page context alone. HubSpot list adds
  // need a list id, which only the operator knows.
  const needsListId =
    suggestion.invokeAction === "hubspot.lists.add_contact" &&
    !String((params.list_id as string) || "").trim()
  const [listId, setListId] = useState("")

  const panelRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Move focus to the panel (or the field that needs filling) — never to the
    // approve button, so a stray Enter keypress cannot commit a write (C.2).
    if (needsListId) inputRef.current?.focus()
    else panelRef.current?.focus()
  }, [needsListId])

  const rows = flattenParams(params).filter((r) => r.key !== "list_id" || !needsListId)

  return (
    <div
      ref={panelRef}
      tabIndex={-1}
      role="group"
      aria-label="Confirm write"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation()
          onCancel()
        }
      }}
      className={cn(
        "gvt-animate-row rounded-lg border bg-card p-3 outline-none",
        destructive ? "border-destructive/40" : "border-primary/40",
      )}
    >
      <div className="flex items-start gap-2">
        {destructive ? (
          <AlertTriangle aria-hidden="true" className="mt-px h-4 w-4 shrink-0 text-destructive" />
        ) : (
          <ShieldCheck aria-hidden="true" className="mt-px h-4 w-4 shrink-0 text-primary" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold leading-snug text-foreground">
            {destructive ? "Confirm this change" : "Confirm this write"}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[12px] leading-relaxed text-muted-foreground">
            <span>Writes to</span>
            <span className="inline-flex items-center gap-1 font-medium text-foreground">
              <ConnectorIcon name={connector} className="h-3 w-3" aria-hidden="true" />
              {connectorLabel(connector)}
            </span>
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
            {suggestion.invokeAction}
          </p>
        </div>
      </div>

      {rows.length > 0 && (
        <div className="mt-2.5">
          <SectionLabel>Data to be written</SectionLabel>
          <dl className="mt-1.5 flex flex-col overflow-hidden rounded-md border border-border bg-secondary/40">
            {rows.map((row) => (
              <div
                key={row.key}
                className="flex items-start gap-2 border-b border-border px-2 py-1.5 last:border-b-0"
              >
                <dt className="w-[74px] shrink-0 text-[11px] text-muted-foreground">
                  {humanizeKey(row.key)}
                </dt>
                <dd className="min-w-0 flex-1 break-words text-[12px] font-medium text-foreground">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {needsListId && (
        <div className="mt-2.5">
          <label
            htmlFor="gvt-list-id"
            className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
          >
            HubSpot list id
          </label>
          <input
            ref={inputRef}
            id="gvt-list-id"
            value={listId}
            onChange={(e) => setListId(e.target.value)}
            placeholder="e.g. 15"
            inputMode="numeric"
            className={cn(
              "mt-1 h-8 w-full rounded-md border border-border bg-background px-2",
              "font-mono text-[12px] text-foreground placeholder:text-muted-foreground",
              "outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          />
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Required before this write can be staged.
          </p>
        </div>
      )}

      {suggestion.note && (
        <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
          {suggestion.note}
        </p>
      )}

      <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Runs with <span className="font-medium text-foreground">catalog_write_authority</span> and
        is recorded in Outcomes.
      </p>

      {error && (
        <p role="alert" className="mt-2 text-[11px] leading-relaxed text-destructive">
          {error}
        </p>
      )}

      <div className="mt-3 flex items-center gap-2">
        <Button
          variant={destructive ? "danger" : "primary"}
          size="sm"
          loading={busy}
          disabled={needsListId && !listId.trim()}
          onClick={() => onApprove(needsListId ? { list_id: listId.trim() } : undefined)}
          className="flex-1"
        >
          {busy ? "Running…" : destructive ? "Approve & change" : "Approve & run"}
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

/**
 * Post-approval confirmation (C.4).
 *
 * Mirrors the main app's Outcomes card: what happened, to which connector, and
 * a direct route to the durable record rather than "go look in Gravitre".
 */
export function OutcomePanel({
  action,
  message,
  onOpenOutcome,
  onDismiss,
}: {
  action?: string
  message?: string
  onOpenOutcome: () => void
  onDismiss: () => void
}) {
  const connector = action ? connectorOf(action) : undefined

  return (
    <div className="gvt-animate-row rounded-lg border border-success/40 bg-success/5 p-3">
      <div className="flex items-start gap-2">
        <span className="mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-success">
          <Check aria-hidden="true" className="h-2.5 w-2.5 text-success-foreground" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold leading-snug text-foreground">
            {connector ? `Written to ${connectorLabel(connector)}` : "Done"}
          </p>
          {action && (
            <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{action}</p>
          )}
          {message && (
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{message}</p>
          )}
        </div>
      </div>
      <div className="mt-2.5 flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={onOpenOutcome} className="flex-1">
          View in Outcomes
          <ArrowUpRight aria-hidden="true" className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="sm" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </div>
  )
}
