"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Blocks, ChevronDown, LayoutGrid, Plus, Rows3, Search, SquareKanban, Store, Target } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { AuPages, paginate } from "@/components/workspace/au-pages"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { ensureSelectedOrg, getQuickOrgId } from "@/lib/org-context"
import { workflowsApi } from "@/lib/api"
import { relativeTime } from "@/lib/agent-job-result"
import { cn } from "@/lib/utils"
import type { WorkflowStatus } from "@/types/api"
import {
  STATE_LABEL,
  filterWorkflows,
  isFailing,
  lastRunDay,
  normalizeWorkflows,
  runTone,
  sortWorkflows,
  successTone,
  summarizeFleet,
  type FleetWorkflow,
  type WorkflowSegment,
  type WorkflowSort,
} from "@/components/workflows/workflow-fleet-model"
import "@/components/workspace/ops-v4.css"
import "@/components/workspace/automate-v1.css"

type WorkflowView = "table" | "cards" | "board"

const PAGE_SIZE = 10

const VIEWS: Array<{ id: WorkflowView; label: string; icon: typeof Rows3 }> = [
  { id: "table", label: "Table", icon: Rows3 },
  { id: "cards", label: "Cards", icon: LayoutGrid },
  { id: "board", label: "Board", icon: SquareKanban },
]

const SORTS: Array<{ id: WorkflowSort; label: string }> = [
  { id: "recent", label: "Recently run" },
  { id: "name", label: "Name" },
  { id: "success", label: "Success rate" },
  { id: "runs", label: "Most runs" },
]

const BOARD_COLUMNS: Array<{ id: Exclude<WorkflowSegment, "all">; label: string }> = [
  { id: "active", label: "Active" },
  { id: "failing", label: "Failing" },
  { id: "paused", label: "Paused" },
  { id: "draft", label: "Draft" },
]

const EXPLAINERS = [
  {
    eyebrow: "01 · Trigger",
    title: "A connector event starts it",
    body: "A new record in a connected app, a schedule or a webhook kicks off the run.",
    art: "/illustrations/spot-connectors.svg",
  },
  {
    eyebrow: "02 · Steps and gates",
    title: "Agents work, writes wait for you",
    body: "Steps that only read run on their own. Steps that change a record can wait for your approval first.",
    art: "/illustrations/ops-approvals.svg",
  },
  {
    eyebrow: "03 · Verified outcome",
    title: "Every run leaves evidence",
    body: "Each run lands in Activity with its steps and results, so success rates come from real runs.",
    art: "/illustrations/ops-activity.svg",
  },
]

function updatedLabel(at: number | null, now: number): string {
  if (at == null) return "Not updated yet"
  const secs = Math.max(0, Math.floor((now - at) / 1000))
  if (secs < 45) return "Updated just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `Updated ${Math.max(1, mins)}m ago`
  return `Updated ${Math.floor(mins / 60)}h ago`
}

function statusTone(workflow: FleetWorkflow): "green" | "amber" | "red" | undefined {
  if (isFailing(workflow)) return "red"
  if (workflow.status === "active") return "green"
  if (workflow.status === "paused") return "amber"
  return undefined
}

function statusLabel(workflow: FleetWorkflow): string {
  if (workflow.isRunning) return "Running"
  if (isFailing(workflow)) return "Failing"
  return STATE_LABEL[workflow.status]
}

export default function WorkflowsPage() {
  return (
    <AppShell title="Workflows">
      <WsPage wide={false}>
        <WorkflowFleet />
      </WsPage>
    </AppShell>
  )
}

function WorkflowFleet() {
  const router = useRouter()
  const { user } = useAuth()
  const [orgId, setOrgId] = useState<string | null>(() => getQuickOrgId())
  const [segment, setSegment] = useState<WorkflowSegment>("all")
  const [runningOnly, setRunningOnly] = useState(false)
  const [query, setQuery] = useState("")
  const [department, setDepartment] = useState("all")
  const [sort, setSort] = useState<WorkflowSort>("recent")
  const [view, setView] = useState<WorkflowView>("table")
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState<"run" | "toggle" | null>(null)
  const [mesonOpen, setMesonOpen] = useState(false)
  const [goalOpen, setGoalOpen] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (user) void ensureSelectedOrg().then(setOrgId)
  }, [user])
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  // Wait for org context so /api/workflows receives x-org-id / org_id (matches Connectors).
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    user && orgId ? `/api/workflows?org_id=${orgId}` : null,
    apiFetcher,
    { revalidateOnFocus: true, refreshInterval: 60_000, onSuccess: () => setUpdatedAt(Date.now()) },
  )

  const workflows = useMemo(() => normalizeWorkflows(data), [data])
  const summary = useMemo(() => summarizeFleet(workflows), [workflows])
  const departments = useMemo(
    () => Array.from(new Set(workflows.flatMap((w) => w.departments))).sort((a, b) => a.localeCompare(b)),
    [workflows],
  )
  const visible = useMemo(
    () => sortWorkflows(filterWorkflows(workflows, { query, segment, department, runningOnly }), sort),
    [workflows, query, segment, department, runningOnly, sort],
  )
  const paged = paginate(visible, page, PAGE_SIZE)
  const selected = visible.find((w) => w.id === selectedId) ?? paged.rows[0] ?? null

  // Only a workflow the user picked becomes AI context; the default first row does not.
  const picked = selectedId ? visible.find((w) => w.id === selectedId) ?? null : null
  usePublishGravitreAISelection(picked ? { kind: "workflow", id: picked.id, label: picked.name } : null)

  useEffect(() => {
    if (paged.page !== page) setPage(paged.page)
  }, [paged.page, page])

  const pickSegment = (next: WorkflowSegment) => {
    setSegment(next)
    setRunningOnly(false)
    setPage(1)
  }

  const runNow = async (workflow: FleetWorkflow) => {
    setBusy("run")
    try {
      const result = await workflowsApi.execute({ workflow_id: workflow.id })
      toast.success(result?.approval_required ? `${workflow.name} is waiting for approval` : `${workflow.name} started`, {
        description: result?.approval_required ? "It runs once someone approves it in Approvals." : result?.run_id ? "Follow it in Activity." : undefined,
        action: result?.run_id ? { label: "Open run", onClick: () => router.push(`/runs/${result.run_id}`) } : undefined,
      })
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start this workflow")
    } finally {
      setBusy(null)
    }
  }

  const toggleStatus = async (workflow: FleetWorkflow) => {
    const next: WorkflowStatus = workflow.status === "active" ? "paused" : "active"
    setBusy("toggle")
    try {
      await workflowsApi.update(workflow.id, { status: next })
      toast.success(`${workflow.name} ${next === "active" ? "activated" : "paused"}`)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update this workflow")
    } finally {
      setBusy(null)
    }
  }

  const loading = isLoading && !data
  const segments: Array<{ id: WorkflowSegment; label: string; count: number; dot: string }> = [
    { id: "all", label: "All", count: summary.all, dot: "ink" },
    { id: "active", label: "Active", count: summary.active, dot: "green" },
    { id: "paused", label: "Paused", count: summary.paused, dot: "amber" },
    { id: "failing", label: "Failing", count: summary.failing, dot: "red" },
    { id: "draft", label: "Draft", count: summary.draft, dot: "" },
  ]
  const showPaused = segment === "paused"

  return (
    <div className="ov-page" data-composition="operate">
      <section aria-labelledby="workflows-hero" className="ov-hero">
        <div className="ov-hero-art">
          {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
          <img src="/illustrations/hero-workflows.svg" alt="" />
          {workflows.length ? (
            <div className="au-art-chip">
              <span className="t">
                <i aria-hidden className={summary.running ? undefined : "idle"} />
                {summary.running ? `${summary.running} running now` : "Nothing running"} · {summary.active} active
              </span>
              <button type="button" aria-pressed={showPaused} onClick={() => pickSegment(showPaused ? "all" : "paused")}>
                {showPaused ? "Show all" : "Show paused"}
              </button>
            </div>
          ) : null}
        </div>
        <div className="ov-hero-copy">
          <div className="ov-hero-eb">
            <span className="ov-eyebrow">Automate / Workflows</span>
            {error && data ? (
              <span className="ov-fresh stale" role="status">
                <i aria-hidden />
                Could not refresh
                <button type="button" onClick={() => void mutate()}>
                  Retry
                </button>
              </span>
            ) : (
              <span className="ov-fresh">
                <i aria-hidden />
                {isValidating && updatedAt ? "Refreshing..." : updatedLabel(updatedAt, now)}
              </span>
            )}
          </div>
          <h1 id="workflows-hero">Workflows</h1>
          <p className="ov-lead">
            Automations across your connectors, with status, runs and failure signals in one place. Steps that write to
            your apps can wait for your OK.
          </p>
          <div className="ov-stats">
            <Stat value={loading ? null : summary.running} label="Running now" tone="green" onClick={() => { pickSegment("all"); setRunningOnly(true) }} />
            <Stat value={loading ? null : summary.active} label="Active" onClick={() => pickSegment("active")} />
            <Stat value={loading ? null : summary.paused} label="Paused" tone={summary.paused ? "amber" : undefined} onClick={() => pickSegment("paused")} />
            <Stat value={loading ? null : summary.failing} label="Failing" tone={summary.failing ? "red" : undefined} onClick={() => pickSegment("failing")} />
          </div>
          <div className="ov-actions">
            <Link className="ov-btn dark" href="/workflows/new/builder">
              <Plus size={16} aria-hidden />
              New workflow
            </Link>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" className="ov-btn">
                  Start from a template
                  <ChevronDown size={14} aria-hidden />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-64">
                <DropdownMenuItem onSelect={() => setGoalOpen(true)} className="flex items-start gap-3 py-2">
                  <Target className="mt-0.5 h-4 w-4 shrink-0" />
                  <span className="flex flex-col">
                    <span className="text-sm font-medium">Create from a goal</span>
                    <span className="text-xs text-muted-foreground">Describe an outcome, review the plan</span>
                  </span>
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setMesonOpen(true)} className="flex items-start gap-3 py-2">
                  <Blocks className="mt-0.5 h-4 w-4 shrink-0" />
                  <span className="flex flex-col">
                    <span className="text-sm font-medium">Build with Meson</span>
                    <span className="text-xs text-muted-foreground">Let Meson draft the steps for you</span>
                  </span>
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => router.push("/marketplace")} className="flex items-start gap-3 py-2">
                  <Store className="mt-0.5 h-4 w-4 shrink-0" />
                  <span className="flex flex-col">
                    <span className="text-sm font-medium">Browse templates</span>
                    <span className="text-xs text-muted-foreground">Install a ready made workflow</span>
                  </span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <AskGravitreSummonButton
              className="au-ask"
              label="Ask Gravitre about failures"
              prompt="Which of my workflows are failing or getting worse, why, and what should I fix first?"
            />
          </div>
        </div>
      </section>

      <section className="ov-panel" aria-labelledby="workflows-list">
        <div className="ov-band">
          <div className="ov-band-l">
            <span className="ov-dots" aria-hidden>
              <i />
              <i />
              <i />
            </span>
            <h2 id="workflows-list">All workflows</h2>
          </div>
          <div className="ov-seg" role="group" aria-label="Filter by status">
            {segments.map((item) => (
              <button key={item.id} type="button" aria-pressed={segment === item.id && !runningOnly} onClick={() => pickSegment(item.id)}>
                <span className={cn("d", item.dot)} aria-hidden />
                {item.label}
                <span className="c">{loading ? "" : item.count}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="au-tools">
          <label className="ov-search">
            <Search size={16} aria-hidden />
            <span className="ov-sr">Search workflows</span>
            <input
              type="search"
              placeholder="Search workflows, apps or departments"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setPage(1)
              }}
            />
          </label>
          {departments.length ? (
            <label className="au-field">
              Department
              <select
                value={department}
                onChange={(e) => {
                  setDepartment(e.target.value)
                  setPage(1)
                }}
              >
                <option value="all">All</option>
                {departments.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="au-field">
            Sort
            <select value={sort} onChange={(e) => setSort(e.target.value as WorkflowSort)}>
              {SORTS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="ov-seg" role="group" aria-label="Layout">
            {VIEWS.map(({ id, label, icon: Icon }) => (
              <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}>
                <Icon size={14} aria-hidden />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="au-split">
          <div className="au-main">
            {error && !data ? (
              <div className="ov-empty" role="alert">
                {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
                <img src="/illustrations/moment-error.svg" alt="" width={160} />
                <b>Failed to load workflows</b>
                <p>We couldn&apos;t reach your workflows. Check your organization context and try again.</p>
                <button type="button" className="ov-btn sm" onClick={() => void mutate()}>
                  Try again
                </button>
              </div>
            ) : loading ? (
              <div className="ov-pad" aria-busy="true">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="ov-skel-n" style={{ display: "block", width: "100%", height: 44, marginBottom: 8 }} />
                ))}
              </div>
            ) : workflows.length === 0 ? (
              <div className="ov-empty">
                {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
                <img src="/illustrations/moment-welcome.svg" alt="" width={160} />
                <b>No workflows yet</b>
                <p>
                  A workflow turns an objective into repeatable steps across your connected systems. Start from a goal, let
                  Meson draft it, or build it step by step.
                </p>
                <div className="ov-actions">
                  <button type="button" className="ov-btn sm dark" onClick={() => setGoalOpen(true)}>
                    Create from a goal
                  </button>
                  <Link className="ov-btn sm" href="/workflows/new/builder">
                    New workflow
                  </Link>
                </div>
              </div>
            ) : visible.length === 0 ? (
              <div className="ov-empty">
                <b>No workflows match</b>
                <button
                  type="button"
                  className="ov-linkbtn"
                  onClick={() => {
                    setQuery("")
                    setDepartment("all")
                    pickSegment("all")
                  }}
                >
                  Clear filters
                </button>
              </div>
            ) : view === "table" ? (
              <div className="au-table-wrap">
                <table className="au-table">
                  <thead>
                    <tr>
                      <th scope="col">Workflow</th>
                      <th scope="col">Status</th>
                      <th scope="col">Department</th>
                      <th scope="col">Last run</th>
                      <th scope="col">Success</th>
                      <th scope="col" className="num">Runs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paged.rows.map((workflow) => (
                      <tr key={workflow.id} aria-selected={selected?.id === workflow.id} onClick={() => setSelectedId(workflow.id)}>
                        <td>
                          <button type="button" className="au-name" onClick={() => setSelectedId(workflow.id)}>
                            <b>{workflow.name}</b>
                            {workflow.description ? <span>{workflow.description}</span> : null}
                          </button>
                        </td>
                        <td>
                          <StatusPill workflow={workflow} />
                        </td>
                        <td>
                          {workflow.departments.length ? (
                            <span className="au-tag">{workflow.departments[0]}</span>
                          ) : (
                            <span className="ov-cell m">None</span>
                          )}
                        </td>
                        <td>
                          <span className="au-mono" title={workflow.lastRun ? relativeTime(workflow.lastRun) : undefined}>
                            {lastRunDay(workflow.lastRun)}
                          </span>
                        </td>
                        <td>
                          <SuccessBar rate={workflow.successRate} complete={workflow.runStatsComplete} runCount={workflow.runCount} />
                        </td>
                        <td className="num au-mono" title={workflow.runStatsComplete ? undefined : "At least this many; the full history was too long to count"}>
                          {workflow.runCount.toLocaleString()}
                          {workflow.runStatsComplete ? "" : "+"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : view === "cards" ? (
              <div className="au-cards">
                {paged.rows.map((workflow) => (
                  <WorkflowCard
                    key={workflow.id}
                    workflow={workflow}
                    selected={selected?.id === workflow.id}
                    onSelect={() => setSelectedId(workflow.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="au-board">
                {BOARD_COLUMNS.map((column) => {
                  const rows = visible.filter((w) => (column.id === "failing" ? isFailing(w) : !isFailing(w) && w.status === column.id))
                  return (
                    <section key={column.id} className="au-col" aria-label={column.label}>
                      <header>
                        <span>{column.label}</span>
                        <small>{rows.length}</small>
                      </header>
                      {rows.length === 0 ? (
                        <p className="au-col-empty">None.</p>
                      ) : (
                        rows.map((workflow) => (
                          <WorkflowCard
                            key={workflow.id}
                            workflow={workflow}
                            compact
                            selected={selected?.id === workflow.id}
                            onSelect={() => setSelectedId(workflow.id)}
                          />
                        ))
                      )}
                    </section>
                  )
                })}
              </div>
            )}

            {visible.length > 0 && view !== "board" ? (
              <div className="au-foot">
                <span>
                  Showing{" "}
                  <b>
                    {paged.from} to {paged.to}
                  </b>{" "}
                  of {visible.length}
                </span>
                <AuPages page={paged.page} pageCount={paged.pageCount} onPage={setPage} label="Workflow pages" />
              </div>
            ) : null}
          </div>

          {selected ? (
            <WorkflowSide
              workflow={selected}
              busy={busy}
              onRun={() => void runNow(selected)}
              onToggle={() => void toggleStatus(selected)}
            />
          ) : null}
        </div>
      </section>

      <section className="au-features" aria-label="How workflows run">
        {EXPLAINERS.map((card) => (
          <article key={card.title} className="au-feature">
            <div className="au-feature-art tall">
              {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
              <img src={card.art} alt="" />
            </div>
            <div className="au-feature-body">
              <span className="au-eyebrow">{card.eyebrow}</span>
              <b>{card.title}</b>
              <p>{card.body}</p>
            </div>
          </article>
        ))}
      </section>

      <MesonWizard
        open={mesonOpen}
        onClose={() => setMesonOpen(false)}
        onComplete={(result) => {
          if (result.workflowId) {
            router.push(`/workflows/${result.workflowId}/builder`)
            return
          }
          if (result.agentId) {
            router.push(`/agents/${result.agentId}`)
            return
          }
          void mutate()
        }}
      />
      <GoalWorkflowWizard open={goalOpen} onOpenChange={setGoalOpen} />
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

function StatusPill({ workflow }: { workflow: FleetWorkflow }) {
  const tone = workflow.isRunning ? "green" : statusTone(workflow)
  return (
    <span className={cn("ov-pill", tone)} style={{ fontWeight: 500, fontSize: 12, padding: "3px 10px" }}>
      <span className="ov-dot" aria-hidden />
      {statusLabel(workflow)}
    </span>
  )
}

function SuccessBar({ rate, complete = true, runCount = 0 }: { rate: number | null; complete?: boolean; runCount?: number }) {
  if (rate === null) {
    // Null with runs means the history was too long to read in full, so no rate is published.
    return <span className="ov-cell m">{!complete || runCount > 0 ? "Not computed" : "No runs"}</span>
  }
  return (
    <span className={cn("au-succ", successTone(rate))}>
      <span className="track" aria-hidden>
        <span style={{ width: `${Math.max(0, Math.min(100, rate))}%` }} />
      </span>
      {rate}%
    </span>
  )
}

function RunBars({ workflow }: { workflow: FleetWorkflow }) {
  if (workflow.recentRuns.length === 0) return <p className="au-runs-empty">No runs yet.</p>
  return (
    <div className="au-runs" role="img" aria-label={`Last ${workflow.recentRuns.length} runs, oldest first`}>
      {workflow.recentRuns.map((run, index) => {
        const tone = runTone(run.status)
        return <i key={`${run.createdAt ?? index}-${index}`} className={tone === "ok" ? undefined : tone} title={run.status} />
      })}
    </div>
  )
}

function WorkflowCard({
  workflow,
  selected,
  compact = false,
  onSelect,
}: {
  workflow: FleetWorkflow
  selected: boolean
  compact?: boolean
  onSelect: () => void
}) {
  const tone = isFailing(workflow) ? "tone-off" : workflow.status === "active" ? "tone-act" : workflow.status === "paused" ? "tone-recommend" : "tone-observe"
  return (
    <button type="button" className={cn("au-card", tone)} aria-pressed={selected} onClick={onSelect}>
      <span className="row">
        <StatusPill workflow={workflow} />
        <small>{workflow.runCount} runs</small>
      </span>
      <b>{workflow.name}</b>
      {compact || !workflow.description ? null : <p>{workflow.description}</p>}
      {compact ? null : <RunBars workflow={workflow} />}
      <span className="row foot">
        {workflow.departments.length ? <span className="au-tag">{workflow.departments[0]}</span> : <span />}
        <SuccessBar rate={workflow.successRate} complete={workflow.runStatsComplete} runCount={workflow.runCount} />
      </span>
    </button>
  )
}

function WorkflowSide({
  workflow,
  busy,
  onRun,
  onToggle,
}: {
  workflow: FleetWorkflow
  busy: "run" | "toggle" | null
  onRun: () => void
  onToggle: () => void
}) {
  return (
    <aside className="au-side" aria-label={`${workflow.name} details`}>
      <div className="ov-chips">
        <StatusPill workflow={workflow} />
        {workflow.departments.map((name) => (
          <span key={name} className="au-tag">
            {name}
          </span>
        ))}
        <span className="au-tag">{workflow.environment === "production" ? "Production" : workflow.environment}</span>
      </div>
      <h3>
        <Link href={`/workflows/${workflow.id}`}>{workflow.name}</Link>
      </h3>
      {workflow.description ? <p className="desc">{workflow.description}</p> : null}

      <div className="au-facts">
        <div className="au-fact">
          <b>{workflow.successRate === null ? (workflow.runCount > 0 ? "n/a" : "None") : `${workflow.successRate}%`}</b>
          <span>Success</span>
        </div>
        <div className="au-fact">
          <b>
            {workflow.runCount.toLocaleString()}
            {workflow.runStatsComplete ? "" : "+"}
          </b>
          <span>{workflow.runStatsComplete ? "Runs" : "Runs (at least)"}</span>
        </div>
        <div className="au-fact">
          <b>{workflow.steps.length}</b>
          <span>Steps</span>
        </div>
      </div>

      <span className="au-eyebrow">Last {Math.max(workflow.recentRuns.length, 1) === 1 ? "run" : `${workflow.recentRuns.length} runs`}</span>
      <RunBars workflow={workflow} />

      {workflow.steps.length ? (
        <>
          <span className="au-eyebrow">Path</span>
          <ol className="au-path">
            {workflow.steps.slice(0, 6).map((step, index) => (
              <li key={`${step}-${index}`}>
                <span className="n">{index + 1}</span>
                <span className="t">{step}</span>
              </li>
            ))}
            {workflow.steps.length > 6 ? <li className="ov-kicker">and {workflow.steps.length - 6} more steps</li> : null}
          </ol>
        </>
      ) : null}

      <div className="au-side-foot">
        {workflow.status === "active" ? (
          <button type="button" className="ov-btn sm green" disabled={busy !== null} onClick={onRun}>
            {busy === "run" ? "Starting..." : "Run now"}
          </button>
        ) : null}
        <Link className="ov-btn sm" href={`/workflows/${workflow.id}/builder`}>
          Edit
        </Link>
        {workflow.status === "active" || workflow.status === "paused" ? (
          <button type="button" className="ov-btn sm" disabled={busy !== null} onClick={onToggle}>
            {busy === "toggle" ? "Saving..." : workflow.status === "active" ? "Pause" : "Activate"}
          </button>
        ) : null}
      </div>
    </aside>
  )
}
