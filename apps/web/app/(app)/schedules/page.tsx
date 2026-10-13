"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { CalendarDays, ChevronLeft, ChevronRight, Columns3, GanttChartSquare, List as ListIcon, Plus } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { ScheduleEditorDialog } from "@/components/schedules/schedule-editor-dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { useSchedules } from "@/lib/use-schedules"
import { runsApi, workflowsApi } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ensureSelectedOrg, getQuickOrgId } from "@/lib/org-context"
import { normalizeApprovals } from "@/components/approvals/decision-queue/model"
import { cn } from "@/lib/utils"
import type { ScheduleOccurrence } from "@/lib/schedules"
import { WeekView } from "./_components/week-view"
import { GanttView } from "./_components/gantt-view"
import { ListView } from "./_components/list-view"
import { ScheduleItemDialog } from "./_components/schedule-item-dialog"
import {
  RUN_STATES,
  RUN_STATE_LABEL,
  addMonths,
  agendaLine,
  buildEntries,
  countStates,
  credentialFailures,
  dayKey,
  groupByDay,
  hotspots,
  latestFailedPerWorkflow,
  monthGrid,
  startOfMonth,
  successPercent,
  timeLabel,
  trimGrid,
  type CalendarEntry,
  type RunState,
} from "./_components/month-model"
import "@/components/workspace/ops-v4.css"
import "@/components/workspace/automate-v1.css"

type CalendarView = "month" | "week" | "timeline" | "list"

const VIEWS: Array<{ id: CalendarView; label: string; icon: typeof CalendarDays }> = [
  { id: "month", label: "Month", icon: CalendarDays },
  { id: "week", label: "Week", icon: Columns3 },
  { id: "timeline", label: "Timeline", icon: GanttChartSquare },
  { id: "list", label: "List", icon: ListIcon },
]

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
const CHIPS_PER_DAY = 2

type ConnectorRow = { id?: string; name?: string; type?: string; status?: string; authStatus?: string }

function needsReconnect(connector: ConnectorRow): boolean {
  return connector.status === "error" || connector.status === "disconnected" || connector.authStatus === "auth_expired"
}

function connectorName(connector: ConnectorRow): string {
  return String(connector.name || connector.type || "a connector")
}

export default function SchedulesPage() {
  return (
    <AppShell title="Schedules">
      <WsPage wide={false}>
        <SchedulesCalendar />
      </WsPage>
    </AppShell>
  )
}

function SchedulesCalendar() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [orgId, setOrgId] = useState<string | null>(() => getQuickOrgId())
  const [month, setMonth] = useState(() => startOfMonth(new Date()))
  const [selectedDay, setSelectedDay] = useState(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  })
  const [view, setView] = useState<CalendarView>("month")
  const [shown, setShown] = useState<Set<RunState>>(() => new Set(RUN_STATES))
  const [department, setDepartment] = useState("all")
  const [createOpen, setCreateOpen] = useState(false)
  const [openOccurrence, setOpenOccurrence] = useState<ScheduleOccurrence | null>(null)
  const [retryScope, setRetryScope] = useState<{ label: string; entries: CalendarEntry[] } | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    if (user) void ensureSelectedOrg().then(setOrgId)
  }, [user])
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000)
    return () => window.clearInterval(timer)
  }, [])

  const grid = useMemo(() => trimGrid(monthGrid(month), month), [month])
  const range = useMemo(() => {
    const from = new Date(grid[0])
    const to = new Date(grid[grid.length - 1])
    to.setHours(23, 59, 59, 999)
    return { from, to }
  }, [grid])

  const { items, isLoading, error, refresh, coverage } = useSchedules({ from: range.from.toISOString(), to: range.to.toISOString() })

  const { data: workflowData } = useSWR(user ? ["schedules-workflows"] : null, () => workflowsApi.list(), {
    revalidateOnFocus: false,
  })
  const workflowRows = useMemo(
    () => ((workflowData?.workflows ?? []) as unknown as Array<{ id: string; name: string; departments?: string[] }>),
    [workflowData],
  )
  const workflowOptions = useMemo(() => workflowRows.map((w) => ({ id: w.id, name: w.name })), [workflowRows])
  const departmentsByWorkflow = useMemo(
    () => new Map(workflowRows.map((w) => [w.id, Array.isArray(w.departments) ? w.departments : []])),
    [workflowRows],
  )
  const departments = useMemo(
    () => Array.from(new Set(workflowRows.flatMap((w) => (Array.isArray(w.departments) ? w.departments : [])))).sort(),
    [workflowRows],
  )

  const { data: connectorData } = useSWR<{ connectors?: ConnectorRow[] }>(
    user && orgId ? `/api/connectors?org=${orgId}` : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const brokenConnectors = useMemo(() => (connectorData?.connectors ?? []).filter(needsReconnect), [connectorData])

  const { data: approvalsData } = useSWR(user ? "/api/approvals" : null, apiFetcher, { revalidateOnFocus: false })
  const pendingApprovals = useMemo(
    () => (approvalsData ? normalizeApprovals(approvalsData).filter((a) => a.status === "pending").length : null),
    [approvalsData],
  )

  const allEntries = useMemo(() => buildEntries(items, range.from, range.to, now), [items, range, now])
  const deptEntries = useMemo(
    () =>
      department === "all"
        ? allEntries
        : allEntries.filter((e) => e.workflowId && (departmentsByWorkflow.get(e.workflowId) ?? []).includes(department)),
    [allEntries, department, departmentsByWorkflow],
  )
  const monthEntries = useMemo(() => deptEntries.filter((e) => e.date.getMonth() === month.getMonth() && e.date.getFullYear() === month.getFullYear()), [deptEntries, month])
  const monthCounts = useMemo(() => countStates(monthEntries), [monthEntries])
  const runningNow = useMemo(() => items.filter((item) => item.status === "running").length, [items])
  const visibleEntries = useMemo(() => deptEntries.filter((e) => shown.has(e.state)), [deptEntries, shown])
  const byDay = useMemo(() => groupByDay(visibleEntries), [visibleEntries])

  const dayEntries = useMemo(() => byDay.get(dayKey(selectedDay)) ?? [], [byDay, selectedDay])
  const dayAll = useMemo(() => groupByDay(deptEntries).get(dayKey(selectedDay)) ?? [], [deptEntries, selectedDay])
  const dayCounts = countStates(dayAll)
  const daySuccess = successPercent(dayAll)
  const isToday = dayKey(selectedDay) === dayKey(now)

  const monthHotspots = useMemo(() => hotspots(monthEntries), [monthEntries])
  const monthCredential = useMemo(() => credentialFailures(monthEntries), [monthEntries])
  const failuresOnly = shown.size === 1 && shown.has("failed")

  const monthLabel = month.toLocaleString(undefined, { month: "long", year: "numeric" })

  const goMonth = (delta: number) => {
    const next = addMonths(month, delta)
    setMonth(next)
    setSelectedDay(next)
  }
  const goToday = () => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    setMonth(startOfMonth(d))
    setSelectedDay(d)
  }
  const toggleState = (state: RunState) => {
    setShown((current) => {
      const next = new Set(current)
      if (next.has(state)) next.delete(state)
      else next.add(state)
      return next.size === 0 ? new Set(RUN_STATES) : next
    })
  }

  const askRetry = (label: string, entries: CalendarEntry[]) => {
    const targets = latestFailedPerWorkflow(entries)
    if (targets.length === 0) {
      toast.message("No failed runs to retry here")
      return
    }
    setRetryScope({ label, entries: targets })
  }

  const runRetry = async () => {
    if (!retryScope) return
    setRetrying(true)
    let started = 0
    const failed: string[] = []
    for (const entry of retryScope.entries) {
      try {
        await runsApi.retry(entry.occurrence.item.id)
        started += 1
      } catch {
        failed.push(entry.name)
      }
    }
    setRetrying(false)
    setRetryScope(null)
    if (started) toast.success(`${started} ${started === 1 ? "workflow" : "workflows"} started again`)
    if (failed.length) toast.error(`Could not retry ${failed.join(", ")}`)
    refresh()
  }

  const occurrencesForViews = visibleEntries.map((e) => e.occurrence)
  const loading = isLoading && items.length === 0

  return (
    <div className="ov-page" data-composition="operate">
      <section aria-labelledby="schedules-hero" className="ov-hero">
        <div className="ov-hero-art">
          {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
          <img src="/illustrations/hero-schedules.svg" alt="" />
          {items.length ? (
            <div className="au-art-chip">
              <span className="t">
                <i aria-hidden className={monthCounts.failed ? "red" : runningNow ? undefined : "idle"} />
                {runningNow} running now · {monthCounts.failed} failed this month
              </span>
              <button
                type="button"
                aria-pressed={failuresOnly}
                onClick={() => setShown(failuresOnly ? new Set(RUN_STATES) : new Set<RunState>(["failed"]))}
              >
                {failuresOnly ? "Show all" : "Show failures"}
              </button>
            </div>
          ) : null}
        </div>
        <div className="ov-hero-copy">
          <div className="ov-hero-eb">
            <span className="ov-eyebrow">Automate / Schedules</span>
            {error && items.length ? (
              <span className="ov-fresh stale" role="status">
                <i aria-hidden />
                Could not refresh
                <button type="button" onClick={refresh}>
                  Retry
                </button>
              </span>
            ) : (
              <span className="ov-fresh">
                <i aria-hidden />
                Live · {monthLabel}
              </span>
            )}
          </div>
          <h1 id="schedules-hero">Schedules</h1>
          <p className="ov-lead">
            Every timed run across your workflows on one calendar. See what is running now, what failed and what comes
            next, then fix the hotspots first.
          </p>
          <div className="ov-stats">
            <Stat value={loading ? null : runningNow} label="Running now" tone="green" onClick={() => setShown(new Set<RunState>(["running"]))} />
            <Stat value={loading ? null : monthCounts.scheduled} label="Scheduled" onClick={() => setShown(new Set<RunState>(["scheduled"]))} />
            <Stat
              value={loading ? null : monthCounts.failed}
              label="Failed this month"
              tone={monthCounts.failed ? "red" : undefined}
              onClick={() => setShown(new Set<RunState>(["failed"]))}
            />
            <Stat value={loading ? null : monthCounts.completed} label="Completed" onClick={() => setShown(new Set<RunState>(["completed"]))} />
          </div>
          <div className="ov-actions">
            <button type="button" className="ov-btn dark" onClick={() => setCreateOpen(true)}>
              <Plus size={16} aria-hidden />
              New schedule
            </button>
            {isAdmin ? (
              <button
                type="button"
                className="ov-btn"
                disabled={monthCounts.failed === 0}
                onClick={() => askRetry(`failed runs in ${monthLabel}`, monthEntries)}
              >
                Retry failed runs
              </button>
            ) : null}
            <AskGravitreSummonButton
              className="au-ask"
              label="Ask Gravitre why runs fail"
              prompt="Why are my scheduled runs failing this month, which workflows fail most, and what should I fix first?"
            />
          </div>
        </div>
      </section>

      <section className="ov-panel" aria-labelledby="schedules-cal">
        <div className="ov-band">
          <div className="ov-band-l au-cal-head">
            <span className="ov-dots" aria-hidden>
              <i />
              <i />
              <i />
            </span>
            <h2 id="schedules-cal">{monthLabel}</h2>
            <button type="button" className="nav" aria-label="Previous month" onClick={() => goMonth(-1)}>
              <ChevronLeft size={16} aria-hidden />
            </button>
            <button type="button" className="ov-btn sm" onClick={goToday}>
              Today
            </button>
            <button type="button" className="nav" aria-label="Next month" onClick={() => goMonth(1)}>
              <ChevronRight size={16} aria-hidden />
            </button>
          </div>
          <div className="ov-seg" role="group" aria-label="Calendar layout">
            {VIEWS.map(({ id, label, icon: Icon }) => (
              <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}>
                <Icon size={14} aria-hidden />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="au-tools">
          <div className="au-show" role="group" aria-label="Show runs">
            <span>Show</span>
            {RUN_STATES.map((state) => (
              <button
                key={state}
                type="button"
                className={cn("au-toggle", `st-${state}`)}
                aria-pressed={shown.has(state)}
                onClick={() => toggleState(state)}
              >
                <i aria-hidden />
                {RUN_STATE_LABEL[state]}
                <small>{state === "running" ? runningNow : monthCounts[state]}</small>
              </button>
            ))}
          </div>
          <span className="sp" />
          {departments.length ? (
            <label className="au-field">
              Department
              <select value={department} onChange={(e) => setDepartment(e.target.value)}>
                <option value="all">All</option>
                {departments.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>

        {coverage !== "complete" && !loading && !error ? (
          <p className="ov-alert" role="status" style={{ margin: "12px 16px 0", color: "var(--ov-amber-ink)", background: "var(--ov-amber-bg)" }}>
            {coverage === "truncated"
              ? "This month has more runs than the calendar loads at once, so the oldest runs in it are not shown and the counts on this page are lower than the real totals."
              : "Only the latest runs are available right now, so this calendar may not show the whole month and its counts may be lower than the real totals."}
          </p>
        ) : null}

        <div className="au-split">
          <div className="au-main">
            {error && items.length === 0 ? (
              <div className="ov-empty" role="alert">
                {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
                <img src="/illustrations/moment-error.svg" alt="" width={160} />
                <b>Couldn&apos;t load schedules</b>
                <p>We couldn&apos;t reach the schedules service. Please try again.</p>
                <button type="button" className="ov-btn sm" onClick={refresh}>
                  Try again
                </button>
              </div>
            ) : view === "month" ? (
              <div className="au-month" aria-busy={loading || undefined}>
                {WEEKDAYS.map((day) => (
                  <div key={day} className="au-wd" aria-hidden>
                    {day}
                  </div>
                ))}
                {grid.map((date) => {
                  const key = dayKey(date)
                  const entries = byDay.get(key) ?? []
                  const out = date.getMonth() !== month.getMonth()
                  const hasFailure = entries.some((e) => e.state === "failed")
                  const shownChips = entries.slice(0, CHIPS_PER_DAY)
                  const label = `${date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}: ${entries.length} ${entries.length === 1 ? "run" : "runs"}${hasFailure ? ", includes failures" : ""}`
                  return (
                    <button
                      key={key}
                      type="button"
                      className={cn("au-day", out && "out", key === dayKey(now) && "today")}
                      aria-pressed={key === dayKey(selectedDay)}
                      aria-label={label}
                      onClick={() => setSelectedDay(date)}
                    >
                      <span className="num">{date.getDate()}</span>
                      {hasFailure ? <span className="flag" aria-hidden /> : null}
                      {shownChips.map((entry) => (
                        <span key={entry.key} className={cn("au-ev", `st-${entry.state}`)} aria-hidden>
                          {timeLabel(entry.date)} {entry.name}
                        </span>
                      ))}
                      {entries.length > CHIPS_PER_DAY ? (
                        <span className="au-more" aria-hidden>
                          +{entries.length - CHIPS_PER_DAY} more
                        </span>
                      ) : null}
                      {entries.length ? (
                        <span className="dots" aria-hidden>
                          {entries.slice(0, 6).map((entry) => (
                            <i key={entry.key} className={`st-${entry.state}`} />
                          ))}
                        </span>
                      ) : null}
                    </button>
                  )
                })}
              </div>
            ) : view === "week" ? (
              <div className="au-board-wrap">
                <WeekView
                  focusDate={selectedDay}
                  occurrences={occurrencesForViews}
                  onSelect={(o) => setSelectedDay(new Date(o.date.getFullYear(), o.date.getMonth(), o.date.getDate()))}
                  onOpen={setOpenOccurrence}
                />
              </div>
            ) : view === "timeline" ? (
              <div className="au-board-wrap">
                <GanttView
                  rangeStart={startOfMonth(month)}
                  rangeEnd={new Date(month.getFullYear(), month.getMonth() + 1, 0, 23, 59, 59)}
                  occurrences={occurrencesForViews}
                  onSelect={(o) => setSelectedDay(new Date(o.date.getFullYear(), o.date.getMonth(), o.date.getDate()))}
                  onOpen={setOpenOccurrence}
                />
              </div>
            ) : (
              <div className="au-board-wrap">
                <ListView
                  items={Array.from(new Map(occurrencesForViews.map((o) => [o.item.id, o.item])).values())}
                  onSelect={() => undefined}
                  onOpen={(item) => {
                    const match = occurrencesForViews.find((o) => o.item.id === item.id)
                    if (match) setOpenOccurrence(match)
                  }}
                />
              </div>
            )}
          </div>

          <aside className="au-side" aria-labelledby="schedules-day">
            <span className="au-eyebrow">Day agenda</span>
            <h3 id="schedules-day">
              {selectedDay.toLocaleDateString(undefined, { weekday: "short", month: "long", day: "numeric" })}
              {isToday ? " · Today" : ""}
            </h3>
            <p className="desc">{isToday ? "Live and completed runs so far" : "Runs and schedules on this day"}</p>
            <div className="au-facts">
              <div className="au-fact">
                <b>{dayAll.length}</b>
                <span>Runs</span>
              </div>
              <div className={cn("au-fact")}>
                <b style={dayCounts.failed ? { color: "var(--ov-red-ink)" } : undefined}>{dayCounts.failed}</b>
                <span>Failed</span>
              </div>
              <div className="au-fact">
                <b>{daySuccess === null ? "None" : `${daySuccess}%`}</b>
                <span>Success</span>
              </div>
            </div>
            {dayEntries.length === 0 ? (
              <p className="ov-side-empty" style={{ padding: 0 }}>
                {loading ? "Loading runs..." : "Nothing on this day for the runs you are showing."}
              </p>
            ) : (
              <ol className="au-agenda">
                {dayEntries.slice(0, 8).map((entry) => (
                  <li key={entry.key} className={`st-${entry.state}`}>
                    <button type="button" onClick={() => setOpenOccurrence(entry.occurrence)}>
                      <time dateTime={entry.date.toISOString()}>{timeLabel(entry.date)}</time>
                      <span className="dot" aria-hidden />
                      <span className="txt">
                        <b>{entry.name}</b>
                        <span>{agendaLine(entry)}</span>
                        {entry.state === "failed" && entry.occurrence.item.error ? <em>{entry.occurrence.item.error}</em> : null}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
            {dayEntries.length > 8 ? (
              <button type="button" className="au-linkbtn" onClick={() => setView("list")}>
                See all {dayEntries.length} runs in List
              </button>
            ) : null}
            <div className="au-side-foot">
              {isAdmin && dayCounts.failed ? (
                <button
                  type="button"
                  className="ov-btn sm green"
                  onClick={() => askRetry(`failed runs on ${selectedDay.toLocaleDateString(undefined, { month: "long", day: "numeric" })}`, dayAll)}
                >
                  Retry failed
                </button>
              ) : null}
              <Link className="ov-btn sm" href="/activity">
                Open in Activity
              </Link>
            </div>
          </aside>
        </div>
      </section>

      <section className="au-features" aria-label="What needs attention">
        <article className="au-hot">
          <header>
            <div>
              <span className="au-eyebrow">Failure hotspots</span>
              <b>{monthHotspots.length ? "Fix these first" : "No failures this month"}</b>
            </div>
            {monthCounts.failed ? (
              <span className="ov-chip red bold">
                {monthCounts.failed} failed
              </span>
            ) : null}
          </header>
          {monthHotspots.length ? (
            <>
              <ol>
                {monthHotspots.map((spot) => (
                  <li key={spot.name}>
                    <span className="n">{spot.name}</span>
                    <span className="track" aria-hidden>
                      <span style={{ width: `${Math.round((spot.count / monthHotspots[0].count) * 100)}%` }} />
                    </span>
                    <small>{spot.count}</small>
                  </li>
                ))}
              </ol>
              <p>
                {monthHotspots[0].name} accounts for {monthHotspots[0].count} of {monthCounts.failed} failures this month.
                {monthCredential
                  ? ` ${monthCredential} ${monthCredential === 1 ? "failure mentions" : "failures mention"} a sign in or credential problem, so reconnecting may clear them.`
                  : ""}
              </p>
            </>
          ) : (
            <p style={{ borderTop: 0, paddingTop: 0 }}>Failed runs will be grouped here by workflow so you can see what to fix first.</p>
          )}
        </article>

        <article className="au-feature">
          <div className="au-feature-art tall">
            {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
            <img src={brokenConnectors.length ? "/illustrations/ops-sources.svg" : "/illustrations/spot-connectors.svg"} alt="" />
          </div>
          <div className="au-feature-body">
            <span className="au-eyebrow">Connections</span>
            {brokenConnectors.length ? (
              <>
                <b>
                  {brokenConnectors.length === 1
                    ? `${connectorName(brokenConnectors[0])} needs to be reconnected`
                    : `${brokenConnectors.length} connections need attention`}
                </b>
                <p>Runs that read from or write to a disconnected app fail until it is reconnected.</p>
                <Link className="ov-btn sm au-feature-act" href="/connectors">
                  {brokenConnectors.length === 1 ? `Reconnect ${connectorName(brokenConnectors[0])}` : "Open connectors"}
                </Link>
              </>
            ) : (
              <>
                <b>{connectorData ? "Every connection is signed in" : "Connections"}</b>
                <p>When a sign in expires, the runs that depend on it fail. You will see it here first.</p>
                <Link className="ov-btn sm au-feature-act" href="/connectors">
                  Open connectors
                </Link>
              </>
            )}
          </div>
        </article>

        <article className="au-feature">
          <div className="au-feature-art tall">
            {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
            <img src="/illustrations/agents-guardrails.svg" alt="" />
          </div>
          <div className="au-feature-body">
            <span className="au-eyebrow">Approvals</span>
            <b>
              {pendingApprovals
                ? `${pendingApprovals} ${pendingApprovals === 1 ? "request is" : "requests are"} waiting for your OK`
                : "Writes wait for your OK"}
            </b>
            <p>Scheduled runs that need approval to change a record pause in Approvals until someone decides.</p>
            <Link className="ov-btn sm au-feature-act" href="/approvals">
              Open approvals
            </Link>
          </div>
        </article>
      </section>

      <ScheduleEditorDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        workflows={workflowOptions}
        onSaved={() => refresh()}
      />
      <ScheduleItemDialog
        occurrence={openOccurrence}
        open={Boolean(openOccurrence)}
        onOpenChange={(open) => (!open ? setOpenOccurrence(null) : undefined)}
        onUpdated={refresh}
        workflowOptions={workflowOptions}
      />
      <AlertDialog open={Boolean(retryScope)} onOpenChange={(open) => (!open && !retrying ? setRetryScope(null) : undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Retry {retryScope?.label}?</AlertDialogTitle>
            <AlertDialogDescription>
              This starts a fresh run of {retryScope?.entries.length === 1 ? "1 workflow" : `${retryScope?.entries.length ?? 0} workflows`}:{" "}
              {retryScope?.entries.map((e) => e.name).join(", ")}. Each workflow is retried once from its latest failed run,
              not once per failure.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={retrying}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={retrying}
              onClick={(event) => {
                event.preventDefault()
                void runRetry()
              }}
            >
              {retrying ? "Retrying..." : "Retry"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function Stat({
  value,
  label,
  tone,
  onClick,
}: {
  value: number | null
  label: string
  tone?: "green" | "amber" | "red"
  onClick: () => void
}) {
  return (
    <button type="button" className={cn("ov-stat", tone)} onClick={onClick}>
      <span className="v">{value === null ? <span className="ov-skel-n" aria-hidden /> : value}</span>
      <span className="k">{label}</span>
    </button>
  )
}
