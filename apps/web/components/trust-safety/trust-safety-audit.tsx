"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "./overlays/toast"
import { useAuth } from "@/lib/auth-context"
import {
  AUDIT_CATEGORIES,
  AUDIT_RANGES,
  exportAudit,
  listAudit,
  rangeStart,
  type AuditCategory,
  type AuditEvent,
  type AuditOutcomeFilter,
  type AuditQuery,
  type AuditRange,
} from "@/lib/settings-api/audit"
import { eventActor, eventEntity, eventTitle, isErrorEvent, pageCountFor } from "@/components/settings/audit-model"
import { Hero, Icon, Pill, TONE } from "./ts-ui"
import { AuditEventPanel, auditErrorText } from "./trust-safety-audit-detail"

const PAGE_SIZE = 6
const COLS = "minmax(0,2.2fr) minmax(0,1.4fr) minmax(0,1.8fr) 110px"

/** 7 day totals for the tab badge, shared with the tab's own unfiltered view. */
export function useAuditTotals() {
  const { user } = useAuth()
  const { data } = useSWR(user ? (["trust-safety/audit/totals", user.id] as const) : null, () =>
    listAudit({ range: "7d" }, rangeStart("7d"), { limit: 1, offset: 0 }),
  { revalidateOnFocus: false, refreshInterval: 120_000 })
  return { errors: data?.errors ?? null, total: data?.total ?? null }
}

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), ms)
    return () => window.clearTimeout(timer)
  }, [value, ms])
  return debounced
}

function timeOf(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  const today = new Date()
  const sameDay = d.toDateString() === today.toDateString()
  return sameDay
    ? d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

const errorText = auditErrorText

function pagesFor(page: number, count: number): Array<number | "…"> {
  if (count <= 5) return Array.from({ length: count }, (_, i) => i + 1)
  const out: Array<number | "…"> = []
  const start = Math.max(1, Math.min(page - 1, count - 3))
  for (let p = start; p <= Math.min(count - 1, start + 2); p++) out.push(p)
  if (start > 1) out.unshift(1, ...(start > 2 ? (["…"] as const) : []))
  if (out[out.length - 1] !== count - 1) out.push("…")
  out.push(count)
  return out
}

export function TrustSafetyAudit() {
  const { user } = useAuth()
  const [search, setSearch] = useState("")
  const [range, setRange] = useState<AuditRange>("7d")
  const [category, setCategory] = useState<AuditCategory | "all">("all")
  const [outcome, setOutcome] = useState<AuditOutcomeFilter>("all")
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)
  const [selected, setSelected] = useState<AuditEvent | null>(null)
  const closeDetails = useCallback(() => setSelected(null), [])
  const q = useDebounced(search.trim())

  useEffect(() => setPage(1), [q, range, category, outcome])

  const query: AuditQuery = useMemo(() => ({ range, category, outcome, q }), [range, category, outcome, q])
  const from = useMemo(() => rangeStart(range), [range])
  const list = useSWR(
    user ? (["trust-safety/audit/list", user.id, range, category, outcome, q, page] as const) : null,
    () => listAudit(query, from, { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    { keepPreviousData: true, refreshInterval: 60_000 },
  )
  // Hero numbers cover the whole range, not the filtered page.
  const totals = useSWR(user ? (["trust-safety/audit/hero", user.id, range] as const) : null, () =>
    listAudit({ range }, from, { limit: 50, offset: 0 }),
  { refreshInterval: 120_000 })

  const logs = list.data?.logs ?? []
  const total = list.data?.total ?? 0
  const pageCount = pageCountFor(total, PAGE_SIZE)

  const allTotal = totals.data?.total ?? null
  const errors = totals.data?.errors ?? null
  const actors = totals.data?.actors ?? null
  const rate = allTotal && errors != null ? `${((errors / allTotal) * 100).toFixed(1)}%` : "–"
  const rangeLabel = AUDIT_RANGES.find((r) => r.id === range)?.label.toLowerCase() ?? "last 7 days"

  // Most common failure in the latest events, so the advice names the real cause.
  const topError = useMemo(() => {
    const counts = new Map<string, number>()
    for (const log of totals.data?.logs ?? []) if (isErrorEvent(log)) counts.set(errorText(log), (counts.get(errorText(log)) ?? 0) + 1)
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null
  }, [totals.data])
  const connectorIssue = topError ? /connector/i.test(topError) : false

  const advice =
    errors == null
      ? "Loading the audit trail."
      : errors === 0
        ? "Nothing failed in this range. Every recorded action finished cleanly."
        : topError
          ? `Most recent failures say “${topError}”. Fix the cause once and the error rate drops.`
          : "Filter to errors to see what failed and who it affected."

  async function download(format: "csv" | "json") {
    if (exporting) return
    setExporting(true)
    try {
      const response = await exportAudit(format, query, from)
      if (!response.ok) throw new Error(`Export failed (${response.status})`)
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `audit-export-${range}.${format}`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${format.toUpperCase()}`)
    } catch {
      toast.error("Failed to export audit logs")
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <Hero
        art="audit"
        eyebrow={`Audit trail · ${rangeLabel}`}
        big={errors == null ? "–" : errors.toLocaleString()}
        bigColor={errors ? "#A3333D" : undefined}
        unit={errors === 0 ? "errors" : "errors need a look"}
        advice={advice}
        actions={
          <>
            <button type="button" className="ts-btn danger sm" onClick={() => setOutcome("err")}>Show errors</button>
            {connectorIssue ? <Link href="/connectors" className="ts-btn dark sm">Fix connector</Link> : null}
          </>
        }
        tiles={[
          { value: allTotal == null ? "–" : allTotal.toLocaleString(), label: "Matching events" },
          { value: actors ?? "–", label: "Active users" },
          { value: errors == null ? "–" : errors.toLocaleString(), label: "Errors", tone: errors ? "bad" : undefined },
          { value: rate, label: "Error rate", tone: errors ? "bad" : undefined },
        ]}
      />
      <section className="ts-card" style={{ overflow: "hidden" }}>
        <div className="ts-cardhead">
          <label className="ts-input">
            <Icon name="search" size={16} />
            <input aria-label="Search events" placeholder="Search events" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <select className="ts-select" aria-label="Range" value={range} onChange={(e) => setRange(e.target.value as AuditRange)}>
            {AUDIT_RANGES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
          <select className="ts-select" aria-label="Action" value={category} onChange={(e) => setCategory(e.target.value as AuditCategory | "all")}>
            <option value="all">All actions</option>
            {AUDIT_CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
          <select className="ts-select" aria-label="Outcome" value={outcome} onChange={(e) => setOutcome(e.target.value as AuditOutcomeFilter)}>
            <option value="all">All outcomes</option>
            <option value="ok">Succeeded</option>
            <option value="err">Errors</option>
          </select>
          <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
            <button type="button" className="ts-btn line sm" disabled={exporting} onClick={() => void download("csv")}><Icon name="csv" size={15} />CSV</button>
            <button type="button" className="ts-btn line sm" disabled={exporting} onClick={() => void download("json")}><Icon name="json" size={15} />JSON</button>
          </div>
        </div>
        <div className="ts-tblwrap">
          <div className="ts-tblin">
            <div className="ts-tr" style={{ ["--cols" as string]: COLS, padding: "0 8px" }}>
              <div className="ts-th">Event</div>
              <div className="ts-th">Actor</div>
              <div className="ts-th">Outcome</div>
              <div className="ts-th">Time</div>
            </div>
            {logs.map((log) => {
              const err = isErrorEvent(log)
              const cfg = !err && log.category === "setting"
              const tone = err ? TONE.bad : cfg ? TONE.warn : TONE.ok
              const entity = eventEntity(log)
              return (
                <div
                  key={log.id}
                  className={`ts-row ts-click${selected?.id === log.id ? " sel" : ""}`}
                  style={{ ["--cols" as string]: COLS, padding: "0 8px" }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Show details for ${eventTitle(log)}`}
                  aria-expanded={selected?.id === log.id}
                  onClick={() => setSelected((cur) => (cur?.id === log.id ? null : log))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      setSelected((cur) => (cur?.id === log.id ? null : log))
                    }
                  }}
                >
                  <div className="ts-td" style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <span className={tone.ico} style={{ width: 32, height: 32, borderRadius: 9 }}><Icon name="events" size={15} /></span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{eventTitle(log)}</div>
                      <div className="ts-mono" style={{ fontSize: 12, color: "#55564F", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {[log.entity_type, entity].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                  </div>
                  <div className="ts-td" style={{ fontSize: 13, color: "#55564F", overflowWrap: "anywhere" }}>{eventActor(log)}</div>
                  <div className="ts-td">
                    <Pill bg={tone.bg} fg={tone.fg} dot={tone.dot} style={{ whiteSpace: "normal" }}>
                      {err ? errorText(log) : cfg ? "Config change" : "Success"}
                    </Pill>
                  </div>
                  <div className="ts-td ts-mono" style={{ fontSize: 12, color: "#55564F" }}>{timeOf(log.created_at)}</div>
                </div>
              )
            })}
            {list.data && logs.length === 0 ? (
              <div style={{ padding: "28px 20px", fontSize: 14, color: "#55564F", borderTop: "1px solid #EFEFEA" }}>No events match these filters.</div>
            ) : null}
            {list.error && !list.data ? (
              <div style={{ padding: "28px 20px", fontSize: 14, color: "#A3333D", borderTop: "1px solid #EFEFEA" }}>The audit trail could not be loaded. It retries on its own.</div>
            ) : null}
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid #EFEFEA" }}>
          <span style={{ fontSize: 13, color: "#55564F" }}>Showing {logs.length} of {total.toLocaleString()} events</span>
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <button type="button" className="ts-pg" disabled={page <= 1} aria-label="Previous page" onClick={() => setPage((p) => p - 1)}>‹</button>
            {pagesFor(page, pageCount).map((p, i) =>
              p === "…" ? (
                <span key={`gap-${i}`} className="ts-pg" style={{ display: "inline-grid", placeItems: "center" }}>…</span>
              ) : (
                <button key={p} type="button" className={`ts-pg${p === page ? " on" : ""}`} aria-current={p === page ? "page" : undefined} onClick={() => setPage(p)}>{p}</button>
              ),
            )}
            <button type="button" className="ts-pg" disabled={page >= pageCount} aria-label="Next page" onClick={() => setPage((p) => p + 1)}>›</button>
          </div>
        </div>
      </section>
      {selected ? <AuditEventPanel log={selected} onClose={closeDetails} /> : null}
    </>
  )
}
