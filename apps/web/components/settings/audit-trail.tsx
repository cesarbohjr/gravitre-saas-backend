"use client"

/**
 * Audit trail (design p19). Rendered by app/(app)/audit/page.tsx inside
 * SettingsShell (Governance group). Filters, search, totals and pagination
 * run on the server (GET /api/audit), so the tiles and the pager count the
 * whole filtered range, not just the visible page. Exports reuse the same
 * filters and cover the whole date range.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import {
  Activity,
  Bot,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  FileJson,
  FileText,
  GitBranch,
  ListChecks,
  MessageSquare,
  RefreshCw,
  Search,
  Settings,
  SlidersHorizontal,
  Table2,
  Users,
  X,
} from "lucide-react"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ApiError } from "@/lib/fetcher"
import {
  AUDIT_CATEGORIES,
  AUDIT_OUTCOMES,
  AUDIT_RANGES,
  auditSummary,
  exportAudit,
  listAudit,
  rangeStart,
  type AuditCategory,
  type AuditEvent,
  type AuditListPayload,
  type AuditOutcomeFilter,
  type AuditQuery,
  type AuditRange,
} from "@/lib/settings-api/audit"
import { formatAuditActionLabel } from "@/lib/audit-summary"
import {
  AUDIT_PAGE_SIZE,
  eventActor,
  eventDescription,
  eventEntity,
  eventLinks,
  eventMeta,
  eventTitle,
  isErrorEvent,
  pageCountFor,
  parseAuditDeepLink,
} from "./audit-model"
import { SettingsShell } from "./settings-shell"
import { SetArt, SetError, SetIco, SetNote, SetPager, SetPill, SetSkeleton, SetTabs, formatAgo, formatMoment } from "./settings-kit"
import "./audit-trail.css"

type View = "tl" | "tb"

const CATEGORY_ICONS: Record<AuditCategory, typeof Activity> = {
  sync: RefreshCw,
  run: GitBranch,
  approve: CheckCircle2,
  agent: Bot,
  member: Users,
  setting: Settings,
  chat: MessageSquare,
}

function iconFor(log: AuditEvent) {
  return (log.category && CATEGORY_ICONS[log.category]) || Activity
}

/** Re-render on an interval so "Updated 2 minutes ago" stays honest. */
function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

function useDebounced<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(id)
  }, [value, delayMs])
  return debounced
}

export function auditErrorMessage(error: unknown): string {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Audit access is unavailable. Check your session, organization permissions, and plan access."
  }
  return "Could not load audit events. Check your connection and try again."
}

export function AuditTrailHeaderActions({
  fetchedAt,
  validating,
  failed,
  exporting,
  onExport,
  onRefresh,
}: {
  fetchedAt: number | null
  validating: boolean
  failed: boolean
  exporting: boolean
  onExport: (format: "csv" | "json") => void
  onRefresh: () => void
}) {
  const now = useNow()
  const ago = fetchedAt ? formatAgo(new Date(fetchedAt).toISOString(), now) : null
  const label = validating
    ? "Updating"
    : failed
      ? "Update failed"
      : ago
        ? `Updated ${ago}`
        : "Not updated yet"
  return (
    <>
      <span className="adt-live" role="status" aria-live="polite">
        <span className={`gs-dot ${failed ? "red" : fetchedAt ? "green gs-live" : "ghost"}`} aria-hidden />
        {label}
      </span>
      <button
        type="button"
        className="gs-btn line sm"
        aria-label="Export audit CSV"
        disabled={exporting}
        onClick={() => onExport("csv")}
      >
        <FileText size={15} aria-hidden />
        CSV
      </button>
      <button
        type="button"
        className="gs-btn line sm"
        aria-label="Export audit JSON"
        disabled={exporting}
        onClick={() => onExport("json")}
      >
        <FileJson size={15} aria-hidden />
        JSON
      </button>
      <button
        type="button"
        className="gs-btn line sm"
        aria-label="Refresh audit events"
        disabled={validating}
        onClick={onRefresh}
      >
        <RefreshCw size={15} aria-hidden className={validating ? "adt-spin" : undefined} />
        Refresh
      </button>
    </>
  )
}

export interface AuditTrailState {
  range: AuditRange
  category: AuditCategory | "all"
  outcome: AuditOutcomeFilter
  search: string
  userId: string
  action: string
  entityType: string
  view: View
  page: number
  open: string | null
}

const INITIAL: AuditTrailState = {
  range: "7d",
  category: "all",
  outcome: "all",
  search: "",
  userId: "",
  action: "",
  entityType: "",
  view: "tl",
  page: 1,
  open: null,
}

/** Audit trail page body. Pass `standalone` to render without the SettingsShell wrapper. */
export function AuditTrail({ standalone = false }: { standalone?: boolean } = {}) {
  const { user } = useAuth()
  const { showAdmin } = useOrgAdmin()
  const [state, setState] = useState<AuditTrailState>(INITIAL)
  const [refreshTick, setRefreshTick] = useState(0)
  const [exporting, setExporting] = useState(false)
  const exportInFlight = useRef(false)
  const deepLinked = useRef(false)

  // Deep links from chat replies and help pages: /audit?category=chat&q=hubspot&event=<id>
  useEffect(() => {
    if (deepLinked.current || typeof window === "undefined") return
    deepLinked.current = true
    const link = parseAuditDeepLink(window.location.search)
    if (Object.keys(link).length === 0) return
    setState((current) => ({
      ...current,
      range: link.range ?? current.range,
      category: link.category ?? current.category,
      outcome: link.outcome ?? current.outcome,
      search: link.q ?? current.search,
      userId: link.userId ?? current.userId,
      action: link.action ?? current.action,
      entityType: link.entityType ?? current.entityType,
      view: link.view ?? current.view,
      open: link.open ?? current.open,
      page: 1,
    }))
  }, [])

  const q = useDebounced(state.search.trim())
  // Recomputed on range change and on Refresh, so "Last 24 hours" slides with time.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const from = useMemo(() => rangeStart(state.range), [state.range, refreshTick])
  const query: AuditQuery = useMemo(
    () => ({
      range: state.range,
      category: state.category,
      outcome: state.outcome,
      q,
      userId: state.userId || undefined,
      action: state.action || undefined,
      entityType: state.entityType || undefined,
    }),
    [state.range, state.category, state.outcome, q, state.userId, state.action, state.entityType],
  )
  const offset = (state.page - 1) * AUDIT_PAGE_SIZE

  const listKey = user
    ? ([
        "settings/audit/list",
        user.id,
        state.range,
        state.category,
        state.outcome,
        q,
        state.userId,
        state.action,
        state.entityType,
        from,
        offset,
      ] as const)
    : null
  const list = useSWR<AuditListPayload & { fetchedAt: number }>(
    listKey,
    async () => ({ ...(await listAudit(query, from, { limit: AUDIT_PAGE_SIZE, offset })), fetchedAt: Date.now() }),
    { keepPreviousData: true, revalidateOnFocus: true, revalidateOnReconnect: true, refreshInterval: 60_000 },
  )
  const summary = useSWR(user ? (["settings/audit/summary", user.id, state.range] as const) : null, () => auditSummary(state.range), {
    revalidateOnFocus: false,
    refreshInterval: 120_000,
  })

  const data = list.data
  const total = data && Number.isFinite(data.total) ? data.total : null
  const pageCount = pageCountFor(total ?? 0)

  // Keep the page in range when filters shrink the result.
  useEffect(() => {
    if (total !== null && state.page > pageCount) setState((current) => ({ ...current, page: pageCount }))
  }, [total, pageCount, state.page])

  const set = useCallback(<K extends keyof AuditTrailState>(key: K, value: AuditTrailState[K]) => {
    setState((current) => ({
      ...current,
      [key]: value,
      page: key === "page" ? (value as number) : key === "view" || key === "open" ? current.page : 1,
    }))
  }, [])

  const refresh = () => {
    setRefreshTick((tick) => tick + 1)
    void list.mutate()
    void summary.mutate()
  }

  async function handleExport(format: "csv" | "json") {
    if (exportInFlight.current) return
    exportInFlight.current = true
    setExporting(true)
    try {
      const response = await exportAudit(format, query, rangeStart(state.range))
      if (!response.ok) throw new Error(`Export failed (${response.status})`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `audit-export-${state.range}.${format}`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      toast.success(`Exported ${format.toUpperCase()}`)
    } catch (exportError) {
      console.error("[audit] export failed:", exportError)
      toast.error("Failed to export audit logs")
    } finally {
      exportInFlight.current = false
      setExporting(false)
    }
  }

  const people = summary.data?.byUser?.filter((row) => row.user_id && row.user_id !== "system") ?? []
  const hasFilters =
    state.category !== "all" ||
    state.outcome !== "all" ||
    q !== "" ||
    state.userId !== "" ||
    state.action !== "" ||
    state.entityType !== ""
  const clearFilters = () =>
    setState((current) => ({ ...current, category: "all", outcome: "all", search: "", userId: "", action: "", entityType: "", page: 1 }))

  const logs = data?.logs ?? []
  const listFailed = Boolean(list.error)
  const firstLoad = list.isLoading && !data

  const actions = (
    <AuditTrailHeaderActions
      fetchedAt={data && !listFailed ? data.fetchedAt : null}
      validating={list.isValidating}
      failed={listFailed}
      exporting={exporting || !user}
      onExport={(format) => void handleExport(format)}
      onRefresh={refresh}
    />
  )

  const tileValue = (value: number | undefined | null) =>
    firstLoad ? (
      <span className="gs-skel adt-tile-skel" aria-label="Loading" />
    ) : value === undefined || value === null ? (
      <span className="adt-tile-na">Unavailable</span>
    ) : (
      value.toLocaleString()
    )

  const body = (
    <>
      <section className="gs-card adt-intro" aria-label="Audit summary">
        <SetArt name="settings-audit" ratio="320 / 170" className="adt-art" />
        <div className="adt-intro-copy">
          <div className="gs-strong">The compliance record for this workspace</div>
          <p>
            Filter by person and action, export for reviews, and confirm every write that chat or an agent made. Linked
            from Settings and from any chat reply that used tools.
          </p>
        </div>
        <div className="adt-tiles">
          <div className="gs-tile">
            <b>{tileValue(total)}</b>
            <span>Matching events</span>
          </div>
          <div className="gs-tile">
            <b>{tileValue(data?.actors)}</b>
            <span>Active users</span>
          </div>
          <div className="gs-tile red">
            <b>{tileValue(data?.errors)}</b>
            <span>Errors</span>
          </div>
        </div>
      </section>

      <section className="gs-card clip" aria-label="Audit events">
        <div className="gs-toolbar adt-toolbar">
          <span className="adt-filters-label">
            <SlidersHorizontal size={15} aria-hidden />
            Filters
          </span>
          <select
            className="gs-select"
            aria-label="Range"
            value={state.range}
            onChange={(event) => set("range", event.target.value as AuditRange)}
          >
            {AUDIT_RANGES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="gs-select"
            aria-label="Action"
            value={state.category}
            onChange={(event) => set("category", event.target.value as AuditCategory | "all")}
          >
            <option value="all">All actions</option>
            {AUDIT_CATEGORIES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="gs-select"
            aria-label="Outcome"
            value={state.outcome}
            onChange={(event) => set("outcome", event.target.value as AuditOutcomeFilter)}
          >
            {AUDIT_OUTCOMES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="gs-select"
            aria-label="Person"
            value={state.userId}
            onChange={(event) => set("userId", event.target.value)}
            disabled={!people.length && !state.userId}
          >
            <option value="">Everyone</option>
            {state.userId && !people.some((row) => row.user_id === state.userId) ? (
              <option value={state.userId}>Selected person</option>
            ) : null}
            {people.map((row) => (
              <option key={row.user_id} value={row.user_id}>
                {row.user_name || "Unknown person"} ({row.count})
              </option>
            ))}
          </select>
          <label className="gs-input adt-search">
            <Search size={15} aria-hidden />
            <input
              type="search"
              aria-label="Search events"
              placeholder="Search events"
              value={state.search}
              onChange={(event) => set("search", event.target.value)}
            />
          </label>
          <SetTabs<View>
            label="View"
            className="adt-view"
            value={state.view}
            onChange={(view) => set("view", view)}
            options={[
              { id: "tl", label: "Timeline", icon: ListChecks },
              { id: "tb", label: "Table", icon: Table2 },
            ]}
          />
        </div>
        {state.action || state.entityType ? (
          <div className="adt-chips">
            {state.action ? (
              <span className="gs-chip">
                Action: {formatAuditActionLabel(state.action)}
                <button type="button" aria-label="Remove action filter" onClick={() => set("action", "")}>
                  <X size={13} aria-hidden />
                </button>
              </span>
            ) : null}
            {state.entityType ? (
              <span className="gs-chip">
                Record type: {state.entityType}
                <button type="button" aria-label="Remove record type filter" onClick={() => set("entityType", "")}>
                  <X size={13} aria-hidden />
                </button>
              </span>
            ) : null}
          </div>
        ) : null}

        {firstLoad ? (
          <SetSkeleton rows={6} label="Loading audit events" />
        ) : listFailed && !data ? (
          <SetError message={auditErrorMessage(list.error)} onRetry={() => void list.mutate()} />
        ) : (
          <>
            {listFailed ? (
              <div role="alert" className="adt-stale">
                <span>{auditErrorMessage(list.error)} Showing the last results that loaded.</span>
                <button type="button" className="gs-btn line sm" onClick={() => void list.mutate()}>
                  Try again
                </button>
              </div>
            ) : null}
            {logs.length === 0 ? (
              <div className="gs-empty adt-empty">
                <p>{hasFilters ? "No events match these filters." : "No events were recorded in this range yet."}</p>
                {hasFilters ? (
                  <button type="button" className="gs-btn line sm" onClick={clearFilters}>
                    Clear filters
                  </button>
                ) : null}
              </div>
            ) : state.view === "tl" ? (
              <ol className="adt-tl" aria-label="Audit timeline">
                {logs.map((log) => (
                  <TimelineRow
                    key={log.id}
                    log={log}
                    open={state.open === log.id}
                    onToggle={() => set("open", state.open === log.id ? null : log.id)}
                  />
                ))}
              </ol>
            ) : (
              <div className="gs-scroll-x">
                <div className="gs-tbl adt-tbl" aria-label="Audit events table">
                  <div className="gs-tr head" aria-hidden>
                    <span className="gs-th">Event</span>
                    <span className="gs-th">Actor</span>
                    <span className="gs-th">When</span>
                    <span className="gs-th">Outcome</span>
                  </div>
                  {logs.map((log) => (
                    <TableRow
                      key={log.id}
                      log={log}
                      open={state.open === log.id}
                      onToggle={() => set("open", state.open === log.id ? null : log.id)}
                    />
                  ))}
                </div>
              </div>
            )}
            {total !== null && total > 0 ? (
              <SetPager
                page={state.page}
                pageCount={pageCount}
                from={offset + 1}
                to={Math.min(offset + logs.length, total)}
                total={total}
                onPage={(page) => set("page", page)}
              />
            ) : null}
          </>
        )}
      </section>

      {data?.truncated ? (
        <SetNote tone="amber">
          This range has more events than the trail scans at once. Totals and pages cover the newest{" "}
          {(data.scanLimit ?? 2000).toLocaleString()} events. Pick a shorter range to see older ones.
        </SetNote>
      ) : null}
      <SetNote icon={FileText}>Exports cover the whole date range, not just this page.</SetNote>
    </>
  )

  if (standalone) {
    return (
      <>
        {user ? actions : null}
        {user ? body : <SetNote>Sign in to view your audit trail.</SetNote>}
      </>
    )
  }

  return (
    <SettingsShell activeSection="audit" isAdmin={showAdmin} actions={user ? actions : undefined}>
      {user ? body : <SetNote>Sign in to view your audit trail.</SetNote>}
    </SettingsShell>
  )
}

function OutcomePill({ log }: { log: AuditEvent }) {
  return isErrorEvent(log) ? (
    <SetPill tone="red" dot>
      Error
    </SetPill>
  ) : (
    <SetPill tone="green" dot>
      Success
    </SetPill>
  )
}

function EventDetails({ log, id }: { log: AuditEvent; id: string }) {
  const meta = eventMeta(log)
  const links = eventLinks(log)
  const description = eventDescription(log)
  const hasRaw = Boolean(log.details && Object.keys(log.details).length > 0)
  return (
    <div id={id} className="adt-details">
      {description ? <p className="adt-desc">{description}</p> : null}
      {meta.length ? (
        <div className="adt-meta">
          {meta.map((tile) => (
            <div key={`${tile.k}-${tile.v}`}>
              <div className="k">{tile.k}</div>
              <div className="v gs-mono">{tile.v}</div>
            </div>
          ))}
        </div>
      ) : (
        <p className="gs-sub">No extra details were recorded for this event.</p>
      )}
      {links.length ? (
        <div className="adt-links">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className="gs-link adt-link">
              {link.label}
              <ExternalLink size={13} aria-hidden />
            </Link>
          ))}
        </div>
      ) : null}
      {hasRaw ? (
        <details className="adt-raw">
          <summary>
            <ChevronDown size={14} aria-hidden />
            Technical details
          </summary>
          <pre>{JSON.stringify(log.details, null, 2)}</pre>
        </details>
      ) : null}
    </div>
  )
}

function TimelineRow({ log, open, onToggle }: { log: AuditEvent; open: boolean; onToggle: () => void }) {
  const detailsId = useId()
  const error = isErrorEvent(log)
  return (
    <li className="adt-ev">
      <SetIco icon={iconFor(log)} tone={error ? "bad" : "mute"} />
      <div className="adt-ev-main">
        <button type="button" className="adt-ev-btn" aria-expanded={open} aria-controls={detailsId} onClick={onToggle}>
          <span className="adt-ev-title">{eventTitle(log)}</span>
          <span className="adt-ev-sub">
            {eventActor(log)} · {formatMoment(log.created_at) ?? "Time not recorded"} ·{" "}
            <span className="gs-mono">{eventEntity(log)}</span>
          </span>
        </button>
        {error && log.error_message ? <div className="adt-err">Error: {log.error_message}</div> : null}
        {open ? <EventDetails log={log} id={detailsId} /> : null}
      </div>
      <OutcomePill log={log} />
    </li>
  )
}

function TableRow({ log, open, onToggle }: { log: AuditEvent; open: boolean; onToggle: () => void }) {
  const detailsId = useId()
  return (
    <div>
      <button
        type="button"
        className={`gs-row adt-row${open ? " sel" : ""}`}
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={onToggle}
      >
        <span className="gs-td">
          <span className="t">{eventTitle(log)}</span>
          <span className="s gs-mono">{eventEntity(log)}</span>
        </span>
        <span className="gs-td adt-td-actor">
          {eventActor(log)}
        </span>
        <span className="gs-td gs-mono adt-td-when">
          {formatMoment(log.created_at) ?? "Not recorded"}
        </span>
        <span className="gs-td">
          <OutcomePill log={log} />
        </span>
      </button>
      {open ? (
        <div className="adt-row-details">
          {isErrorEvent(log) && log.error_message ? <div className="adt-err">Error: {log.error_message}</div> : null}
          <EventDetails log={log} id={detailsId} />
        </div>
      ) : null}
    </div>
  )
}
