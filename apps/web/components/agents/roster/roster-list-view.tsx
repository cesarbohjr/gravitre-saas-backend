"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { agentsApi } from "@/lib/api"
import { mapFleetDepartmentToApi } from "@/lib/agent-identity-bridge"
import { models as MODEL_OPTIONS } from "@/components/gravitre/model-selector"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import type { Agent as ApiAgent } from "@/types/api"
import {
  DEPARTMENT_BY_ID,
  ROSTER_DEPARTMENTS,
  blockedReason,
  emptyDepartments,
  formatLastActive,
  formatRate,
  needsYou,
  type RosterAgent,
} from "@/lib/agents-roster"
import { cn } from "@/lib/utils"
import { DepartmentGlyph } from "@/components/agents/department-icon"
import { AgentAvatar, AppChips, GiveTaskLink, agentHref, newAgentHref } from "./agent-bits"

type SortKey = "tasks" | "name"

const STATUS_PILL: Record<RosterAgent["state"], { label: string; cls: string }> = {
  working: { label: "Working", cls: "rs-pill-today" },
  active_today: { label: "Active today", cls: "rs-pill-today" },
  ready: { label: "Available", cls: "rs-pill-ok" },
  blocked: { label: "Needs you", cls: "rs-pill-warn" },
  not_set_up: { label: "Not set up", cls: "rs-pill-off" },
}

function matches(agent: RosterAgent, q: string): boolean {
  if (!q) return true
  return [agent.name, agent.role, agent.departmentLabel, agent.description, agent.model, ...agent.apps]
    .join(" ")
    .toLowerCase()
    .includes(q)
}

function Chevron() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

function Insights({ agents, statsAvailable }: { agents: RosterAgent[]; statsAvailable: boolean }) {
  const ran = agents.filter((a) => a.tasksToday > 0)
  const idle = agents.length - ran.length
  const blocked = needsYou(agents)
  const uncovered = emptyDepartments(agents)
  const first = blocked[0]
  const firstReason = first ? blockedReason(first) : null
  return (
    <section aria-label="Roster insights" className="rs-insights">
      <Link className="rs-ins" href="/assignments/new">
        <span className="ic ok">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden>
            <path d="M7 4.5v15l12-7.5z" />
          </svg>
        </span>
        <div>
          <div className="big">
            {statsAvailable ? idle : "–"} <small>idle today</small>
          </div>
          <div className="body">
            {!statsAvailable
              ? "Today's runs are not reported yet. "
              : ran.length === 0
                ? "No agent has run a task today. "
                : ran.length === 1
                  ? `Only ${ran[0].name} has run today. `
                  : `${ran.length} agents have run today. `}
            {idle > 0 ? "Put the rest to work →" : "Give someone a new task →"}
          </div>
        </div>
      </Link>
      {first ? (
        <Link className="rs-ins warn" href={blocked.length === 1 ? agentHref(first.id) : "/agents?view=list&status=needs"}>
          <span className="ic amber">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M12 3 2 20h20z" />
              <path d="M12 10v4M12 17h.01" />
            </svg>
          </span>
          <div>
            <div className="big">
              {blocked.length} <small>needs attention</small>
            </div>
            <div className="body">
              {blocked.length === 1
                ? `${first.name}: ${firstReason ? firstReason.charAt(0).toLowerCase() + firstReason.slice(1) : "needs a look"} →`
                : `${first.name} and ${blocked.length - 1} more are blocked →`}
            </div>
          </div>
        </Link>
      ) : (
        <div className="rs-ins" style={{ cursor: "default" }}>
          <span className="ic ok">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="m5 12.5 4.5 4.5L19 7.5" />
            </svg>
          </span>
          <div>
            <div className="big">
              0 <small>need attention</small>
            </div>
            <div className="body">Nothing is blocked right now.</div>
          </div>
        </div>
      )}
      {uncovered.length > 0 ? (
        <Link className="rs-ins" href={newAgentHref(uncovered[0].name)}>
          <span className="ic">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
              <circle cx="12" cy="12" r="8.5" strokeDasharray="3 3" />
              <path d="M12 8v8M8 12h8" />
            </svg>
          </span>
          <div>
            <div className="big">
              {uncovered.length === 1 ? (
                <>
                  0 <small>in {uncovered[0].name}</small>
                </>
              ) : (
                <>
                  {uncovered.length} <small>departments uncovered</small>
                </>
              )}
            </div>
            <div className="body">
              {uncovered.length === 1
                ? "One department has no coverage yet. Add an agent →"
                : `${uncovered.map((d) => d.name).join(", ")} have no agents yet. Add one to ${uncovered[0].name} →`}
            </div>
          </div>
        </Link>
      ) : (
        <div className="rs-ins" style={{ cursor: "default" }}>
          <span className="ic ok">{ROSTER_DEPARTMENTS.length}</span>
          <div>
            <div className="big">
              {ROSTER_DEPARTMENTS.length} <small>departments covered</small>
            </div>
            <div className="body">Every department has at least one agent.</div>
          </div>
        </div>
      )}
    </section>
  )
}

/** Rows per page; "View all" lifts the limit. */
export const LIST_PAGE_SIZE = 10

/** Page numbers to show: all when few, otherwise first, last and a window around the current page. */
export function pageItems(page: number, pages: number): Array<number | "gap"> {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1)
  const out: Array<number | "gap"> = [1]
  const from = Math.max(2, page - 1)
  const to = Math.min(pages - 1, page + 1)
  if (from > 2) out.push("gap")
  for (let n = from; n <= to; n++) out.push(n)
  if (to < pages - 1) out.push("gap")
  out.push(pages)
  return out
}

function isDepartment(value: string | null | undefined): value is AgentDepartmentId {
  return Boolean(value) && ROSTER_DEPARTMENTS.some((d) => d.id === value)
}

export function RosterListView({
  agents,
  statsAvailable,
  initialStatus,
  initialDept,
  onChanged,
  onSelectionChange,
}: {
  agents: RosterAgent[]
  statsAvailable: boolean
  initialStatus?: string | null
  /** Department to filter by on arrival, e.g. from a team band's View all. */
  initialDept?: string | null
  onChanged: () => Promise<unknown>
  onSelectionChange?: (agent: RosterAgent | null) => void
}) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [dept, setDeptState] = useState<AgentDepartmentId | "all">(isDepartment(initialDept) ? initialDept : "all")
  const [page, setPage] = useState(1)
  const [showAll, setShowAll] = useState(false)
  const setDept = (next: AgentDepartmentId | "all") => {
    setDeptState(next)
    setPage(1)
  }
  const [needsOnly, setNeedsOnly] = useState(initialStatus === "needs")
  const [sort, setSort] = useState<SortKey>("tasks")
  const [sel, setSel] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [rowBusy, setRowBusy] = useState<string | null>(null)

  const counts = useMemo(() => {
    const map = new Map<AgentDepartmentId, number>()
    for (const a of agents) map.set(a.department, (map.get(a.department) ?? 0) + 1)
    return map
  }, [agents])

  const q = query.trim().toLowerCase()
  const rows = useMemo(() => {
    const list = agents.filter(
      (a) => (dept === "all" || a.department === dept) && (!needsOnly || a.state === "blocked") && matches(a, q),
    )
    return list.sort((x, y) =>
      sort === "tasks" ? y.tasksToday - x.tasksToday || x.name.localeCompare(y.name) : x.name.localeCompare(y.name),
    )
  }, [agents, dept, needsOnly, q, sort])

  const pages = Math.max(1, Math.ceil(rows.length / LIST_PAGE_SIZE))
  const current = Math.min(page, pages)
  const pageRows = showAll ? rows : rows.slice((current - 1) * LIST_PAGE_SIZE, current * LIST_PAGE_SIZE)
  const firstShown = rows.length === 0 ? 0 : showAll ? 1 : (current - 1) * LIST_PAGE_SIZE + 1
  const lastShown = showAll ? rows.length : Math.min(rows.length, current * LIST_PAGE_SIZE)
  const rangeLabel =
    rows.length === 0
      ? `No agents match (${agents.length} in total)`
      : showAll || rows.length <= LIST_PAGE_SIZE
        ? `Showing all ${rows.length} ${rows.length === 1 ? "agent" : "agents"}`
        : `Showing ${firstShown} to ${lastShown} of ${rows.length} agents`

  const selected = agents.filter((a) => sel.includes(a.id))
  const visibleIds = pageRows.map((r) => r.id)
  const allOn = pageRows.length > 0 && visibleIds.every((id) => sel.includes(id))
  const maxTasks = Math.max(1, ...agents.map((a) => a.tasksToday))

  const setSelection = (next: string[]) => {
    setSel(next)
    onSelectionChange?.(next.length === 1 ? agents.find((a) => a.id === next[0]) ?? null : null)
  }
  const toggle = (id: string) => setSelection(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id])

  async function runBulk(label: string, fn: (agent: RosterAgent) => Promise<unknown>) {
    if (selected.length === 0) return
    setBusy(true)
    const results = await Promise.allSettled(selected.map(fn))
    const failed = results.filter((r) => r.status === "rejected").length
    setBusy(false)
    await onChanged()
    if (failed === 0) {
      toast.success(`${label} ${selected.length === 1 ? selected[0].name : `${selected.length} agents`}`)
      setSelection([])
    } else {
      toast.error(`${failed} of ${selected.length} could not be updated. Try again.`)
    }
  }

  async function moveOne(agent: RosterAgent, to: AgentDepartmentId) {
    if (to === agent.department) return
    const label = mapFleetDepartmentToApi(to)
    setRowBusy(agent.id)
    try {
      await agentsApi.update(agent.id, { department: label as ApiAgent["department"] })
      await onChanged()
      toast.success(`${agent.name} moved to ${label}`)
    } catch {
      toast.error(`Could not move ${agent.name}. Try again.`)
    } finally {
      setRowBusy(null)
    }
  }

  const giveThem = () => {
    if (selected.length === 1) router.push(`/assignments/new?agent=${encodeURIComponent(selected[0].id)}`)
    else router.push("/multi-agent-run")
  }

  return (
    <>
      <Insights agents={agents} statsAvailable={statsAvailable} />
      <section className="gv-card rs-listcard" aria-labelledby="rs-list-heading">
        <div className="rs-listhead">
          <div>
            <h2 id="rs-list-heading">{dept === "all" ? "All agents" : `${DEPARTMENT_BY_ID.get(dept)?.name ?? "Department"} agents`}</h2>
            <span>{rangeLabel}</span>
          </div>
          <Link className="gv-btn outline rs-backteam" href="/agents?view=team" replace scroll={false}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M19 12H5M11 6l-6 6 6 6" />
            </svg>
            Back to team view
          </Link>
        </div>
        <div className="rs-listbar">
          <label className="gv-field">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              type="search"
              aria-label="Search agents"
              placeholder="Search agents, roles or apps"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setPage(1)
              }}
            />
          </label>
          <div className="rs-chips" role="group" aria-label="Filter by department" style={{ gap: 6 }}>
            <button
              type="button"
              className={cn("gv-fchip", dept === "all" && "on")}
              aria-pressed={dept === "all"}
              onClick={() => setDept("all")}
            >
              <span className="rs-ddot" />
              All <b>{agents.length}</b>
            </button>
            {ROSTER_DEPARTMENTS.map((d) => (
              <button
                key={d.id}
                type="button"
                className={cn("gv-fchip", `rs-d-${d.id}`, dept === d.id && "on")}
                aria-pressed={dept === d.id}
                onClick={() => setDept(d.id)}
              >
                <DepartmentGlyph department={d.id} size={13} />
                {d.name} <b>{counts.get(d.id) ?? 0}</b>
              </button>
            ))}
            {needsOnly ? (
              <button type="button" className="gv-fchip on" aria-pressed onClick={() => {
                setNeedsOnly(false)
                setPage(1)
              }}>
                Needs you ✕
              </button>
            ) : null}
          </div>
        </div>

        {selected.length > 0 ? (
          <div className="rs-bulk gv-rise" role="region" aria-label="Bulk actions">
            <strong>{selected.length} selected</strong>
            <button type="button" className="gv-btn inv sm" onClick={giveThem} disabled={busy}>
              Give them a task
            </button>
            <label className="sr-only" htmlFor="rs-bulk-dept">
              Move to department
            </label>
            <select
              id="rs-bulk-dept"
              value=""
              disabled={busy}
              onChange={(e) => {
                const to = e.target.value as AgentDepartmentId
                if (!to) return
                const label = mapFleetDepartmentToApi(to)
                void runBulk(`Moved to ${label}:`, (a) =>
                  a.department === to ? Promise.resolve() : agentsApi.update(a.id, { department: label as ApiAgent["department"] }),
                )
              }}
            >
              <option value="">Move to department</option>
              {ROSTER_DEPARTMENTS.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            <label className="sr-only" htmlFor="rs-bulk-model">
              Change model
            </label>
            <select
              id="rs-bulk-model"
              value=""
              disabled={busy}
              onChange={(e) => {
                const model = e.target.value
                if (!model) return
                const name = MODEL_OPTIONS.find((m) => m.id === model)?.name ?? model
                void runBulk(`Switched to ${name}:`, (a) => agentsApi.update(a.id, { model }))
              }}
            >
              <option value="">Change model</option>
              {MODEL_OPTIONS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="gv-btn inv sm"
              disabled={busy}
              onClick={() => void runBulk("Paused", (a) => agentsApi.stop(a.id))}
            >
              Pause
            </button>
            <button type="button" className="gv-btn sm clear" onClick={() => setSelection([])}>
              Clear
            </button>
          </div>
        ) : null}

        <div className="rs-tablewrap">
          <table className="rs-table">
            <thead>
              <tr>
                <th style={{ width: 44 }}>
                  <input
                    type="checkbox"
                    className="gv-check"
                    aria-label="Select all agents"
                    checked={allOn}
                    onChange={() =>
                      setSelection(allOn ? sel.filter((id) => !visibleIds.includes(id)) : [...new Set([...sel, ...visibleIds])])
                    }
                  />
                </th>
                <th aria-sort={sort === "name" ? "ascending" : "none"}>
                  <button type="button" className="rs-sort" onClick={() => setSort("name")}>
                    Agent {sort === "name" ? "↓" : ""}
                  </button>
                </th>
                <th>Department</th>
                <th>Status</th>
                <th aria-sort={sort === "tasks" ? "descending" : "none"}>
                  <button type="button" className="rs-sort" onClick={() => setSort("tasks")}>
                    Tasks today {sort === "tasks" ? "↓" : ""}
                  </button>
                </th>
                <th title="Completed vs failed tasks, last 7 days">Success</th>
                <th>Apps</th>
                <th>Model</th>
                <th>Last active</th>
                <th style={{ width: 150 }}>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((a) => {
                const on = sel.includes(a.id)
                const pill = STATUS_PILL[a.state]
                const rate = formatRate(a.success7d)
                return (
                  <tr key={a.id} className={cn(on && "sel")}>
                    <td>
                      <input
                        type="checkbox"
                        className="gv-check"
                        aria-label={`Select ${a.name}`}
                        checked={on}
                        onChange={() => toggle(a.id)}
                      />
                    </td>
                    <td>
                      <div className="rs-agentcell">
                        <AgentAvatar agent={a} />
                        <div style={{ minWidth: 0 }}>
                          <Link href={agentHref(a.id)}>{a.name}</Link>
                          {a.role ? <div className="rs-sub">{a.role}</div> : null}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={cn("rs-dept", `rs-d-${a.department}`)}>
                        <DepartmentGlyph department={a.department} size={13} />
                        <select
                          aria-label={`Change department for ${a.name}`}
                          value={a.department}
                          disabled={rowBusy === a.id}
                          onChange={(e) => void moveOne(a, e.target.value as AgentDepartmentId)}
                        >
                          {ROSTER_DEPARTMENTS.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.name}
                            </option>
                          ))}
                        </select>
                        <Chevron />
                      </span>
                    </td>
                    <td>
                      <span className={cn("gv-pill", pill.cls)} title={a.state === "blocked" ? blockedReason(a) ?? undefined : undefined}>
                        <span
                          className="gv-dot"
                          style={{
                            width: 7,
                            height: 7,
                            background:
                              a.state === "blocked"
                                ? "var(--gv-amber)"
                                : a.state === "not_set_up"
                                  ? "var(--gv-border-strong)"
                                  : "var(--gv-accent)",
                          }}
                        />
                        {pill.label}
                      </span>
                    </td>
                    <td>
                      {statsAvailable ? (
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ fontWeight: 600, minWidth: 14 }}>{a.tasksToday}</span>
                          <span className="rs-bar" aria-hidden>
                            <span style={{ width: `${Math.round((a.tasksToday / maxTasks) * 100)}%` }} />
                          </span>
                        </div>
                      ) : (
                        <span className="rs-quiet">Not reported</span>
                      )}
                    </td>
                    <td style={{ fontWeight: 600, color: rate ? "var(--gv-brand-strong)" : undefined }}>
                      {rate ?? <span className="rs-quiet">No runs yet</span>}
                    </td>
                    <td>
                      <AppChips apps={a.apps} max={3} />
                    </td>
                    <td className="gv-mono" style={{ fontSize: 12, color: "var(--gv-muted)" }}>
                      {a.model}
                    </td>
                    <td style={{ color: "var(--gv-muted)", fontSize: 13 }}>
                      {statsAvailable ? formatLastActive(a.lastActiveAt) : "Not reported"}
                    </td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <GiveTaskLink agent={a} />
                    </td>
                  </tr>
                )
              })}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={10}>
                    <div className="gv-empty" style={{ margin: 8 }}>
                      No agents match. Try another search or department.
                    </div>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        {rows.length > LIST_PAGE_SIZE ? (
          <nav className="rs-listfoot" aria-label="Pagination">
            <span>{showAll ? "Showing every agent on one page" : `Page ${current} of ${pages}, ${LIST_PAGE_SIZE} per page`}</span>
            <div className="rs-pager">
              {showAll ? (
                <button
                  type="button"
                  className="rs-pg"
                  onClick={() => {
                    setShowAll(false)
                    setPage(1)
                  }}
                >
                  Show {LIST_PAGE_SIZE} per page
                </button>
              ) : (
                <>
                  <button type="button" className="rs-pg" disabled={current === 1} onClick={() => setPage(current - 1)}>
                    Previous
                  </button>
                  {pageItems(current, pages).map((item, i) =>
                    item === "gap" ? (
                      <span key={`gap-${i}`} className="rs-pg-gap" aria-hidden>
                        ...
                      </span>
                    ) : (
                      <button
                        key={item}
                        type="button"
                        className={cn("rs-pg num", item === current && "on")}
                        aria-label={`Page ${item}`}
                        aria-current={item === current ? "page" : undefined}
                        onClick={() => setPage(item)}
                      >
                        {item}
                      </button>
                    ),
                  )}
                  <button type="button" className="rs-pg" disabled={current === pages} onClick={() => setPage(current + 1)}>
                    Next
                  </button>
                  <span className="rs-pg-sep" aria-hidden />
                  <button type="button" className="rs-pg on" onClick={() => setShowAll(true)}>
                    View all {rows.length}
                  </button>
                </>
              )}
            </div>
          </nav>
        ) : (
          <div className="rs-listfoot">
            <span>Tip: select several agents to move or brief them together</span>
          </div>
        )}
      </section>
    </>
  )
}
