"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import type { AuditEvent } from "@/lib/settings-api/audit"
import { eventActor, eventDescription, eventEntity, eventLinks, eventMeta, eventTitle, isErrorEvent } from "@/components/settings/audit-model"
import { Icon, Pill, TONE } from "./ts-ui"

export function auditErrorText(log: AuditEvent): string {
  const details = (log.details ?? {}) as Record<string, unknown>
  for (const raw of [log.error_message, details.error, details.error_message, details.errorMessage, details.failure_reason, details.failureReason]) {
    if (typeof raw === "string" && raw.trim()) return raw.trim()
  }
  return "Failed"
}

function fullTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" })
}

/** Right side panel with everything one audit event recorded. Escape or Hide closes it. */
export function AuditEventPanel({ log, onClose }: { log: AuditEvent; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  useEffect(() => setShowRaw(false), [log.id])

  const err = isErrorEvent(log)
  const cfg = !err && log.category === "setting"
  const tone = err ? TONE.bad : cfg ? TONE.warn : TONE.ok
  const description = eventDescription(log)
  const meta = eventMeta(log, 24)
  const links = eventLinks(log)
  const entity = eventEntity(log)
  const raw = JSON.stringify(log.details ?? {}, null, 2)
  const hasRaw = raw !== "{}"

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(log, null, 2))
      toast.success("Event copied")
    } catch {
      toast.error("Could not copy the event")
    }
  }

  return (
      <aside className="ts-panel" role="dialog" aria-modal="false" aria-labelledby="ts-event-title">
        <div className="ts-panelhead">
          <span className={tone.ico} style={{ width: 36, height: 36, borderRadius: 10, flex: "0 0 auto" }}><Icon name="events" size={16} /></span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div id="ts-event-title" style={{ fontWeight: 600, fontSize: 16 }}>{eventTitle(log)}</div>
            <div className="ts-mono" style={{ fontSize: 12, color: "#6A6B64", marginTop: 2, overflowWrap: "anywhere" }}>{log.action}</div>
          </div>
          <button ref={closeRef} type="button" className="ts-btn line sm" onClick={onClose} aria-label="Hide event details">
            <Icon name="x" size={14} />Hide
          </button>
        </div>
        <div className="ts-panelbody">
          <div>
            <Pill bg={tone.bg} fg={tone.fg} dot={tone.dot}>{err ? "Failed" : cfg ? "Config change" : "Succeeded"}</Pill>
          </div>
          {err ? (
            <div className="ts-panelerr" role="alert">
              <div style={{ fontWeight: 600, marginBottom: 4 }}>What failed</div>
              <div style={{ overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{auditErrorText(log)}</div>
            </div>
          ) : null}
          {description ? <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5, color: "#3E3F3A" }}>{description}</p> : null}
          <dl className="ts-kv">
            <dt>When</dt><dd>{fullTime(log.created_at)}</dd>
            <dt>Actor</dt><dd>{eventActor(log)}</dd>
            {log.user_email && log.user_email !== eventActor(log) ? (<><dt>Email</dt><dd>{log.user_email}</dd></>) : null}
            {log.entity_type ? (<><dt>Record type</dt><dd>{log.entity_type}</dd></>) : null}
            {entity ? (<><dt>Record</dt><dd>{entity}</dd></>) : null}
            {meta.map((tile) => (
              <div key={tile.k} style={{ display: "contents" }}><dt>{tile.k}</dt><dd className="ts-mono">{tile.v}</dd></div>
            ))}
            {log.user_agent ? (<><dt>Client</dt><dd>{log.user_agent}</dd></>) : null}
            <dt>Event ID</dt><dd className="ts-mono">{log.id}</dd>
          </dl>
          {links.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {links.map((link) => <Link key={link.href} href={link.href} className="ts-btn line sm">{link.label}</Link>)}
            </div>
          ) : null}
          {hasRaw ? (
            <div>
              <button type="button" className="ts-btn text sm" style={{ paddingLeft: 0 }} aria-expanded={showRaw} onClick={() => setShowRaw((v) => !v)}>
                {showRaw ? "Hide raw details" : "Show raw details"}
              </button>
              {showRaw ? <pre className="ts-mono ts-raw">{raw}</pre> : null}
            </div>
          ) : null}
        </div>
        <div className="ts-panelfoot">
          <button type="button" className="ts-btn line sm" onClick={() => void copy()}><Icon name="copy" size={14} />Copy event</button>
        </div>
      </aside>
  )
}
