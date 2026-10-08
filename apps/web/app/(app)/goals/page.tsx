"use client"

import { useCallback, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { LayoutList, Plus, RefreshCw, Search, SquareKanban } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
import { GoalBoardCard, GoalCard } from "@/components/goals/goal-card"
import { apiFetch } from "@/lib/fetcher"
import {
  fetchGoalList,
  GOALS_REFRESH_KEY,
  type GoalRecord,
  type GoalStatus,
} from "@/lib/goals-list"
import { ASSIGNMENTS_REFRESH_KEY, fetchAssignmentList } from "@/lib/assignments-list"
import {
  GOAL_STATUS_TABS,
  GOAL_TEMPLATES,
  type GoalTemplate,
  departmentLabel,
  findRelatedAssignment,
  goalMetrics,
  goalStatusOf,
  priorityRank,
} from "@/lib/goal-insights"
import { cn } from "@/lib/utils"
import "@/components/goals/goals.css"

type Tab = GoalStatus | "unreported"
type Sort = "recent" | "due" | "priority"

const HOW_IT_RUNS = [
  { t: "Define the outcome", d: "One sentence, one number, one date." },
  { t: "Gravitre drafts a plan", d: "Agents, workflows and data it will use." },
  { t: "You approve the gates", d: "Writes to CRM or email always pause first." },
  { t: "Progress reports itself", d: "Every run moves the number, with evidence." },
]

function dueTime(goal: GoalRecord): number {
  const due = goalMetrics(goal).dueDate
  const t = due ? Date.parse(due) : Number.NaN
  return Number.isFinite(t) ? t : Number.POSITIVE_INFINITY
}

export default function GoalsPage() {
  const [search, setSearch] = useState("")
  const [department, setDepartment] = useState("")
  const [order, setOrder] = useState<Sort>("recent")
  const [view, setView] = useState<"list" | "board">("list")
  const [picked, setPicked] = useState<Tab | null>(null)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [editing, setEditing] = useState<GoalRecord | null>(null)
  const [template, setTemplate] = useState<GoalTemplate | null>(null)
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    GOALS_REFRESH_KEY,
    fetchGoalList,
    { refreshInterval: 30_000 },
  )
  const allGoals = useMemo(() => data ?? [], [data])
  const { data: assignments } = useSWR(
    allGoals.length > 0 ? ASSIGNMENTS_REFRESH_KEY : null,
    fetchAssignmentList,
    { revalidateOnFocus: false },
  )

  const countOf = useCallback(
    (status: Tab) => allGoals.filter((g) => goalStatusOf(g) === status).length,
    [allGoals],
  )
  const tabs = [
    ...GOAL_STATUS_TABS,
    ...(countOf("unreported") > 0
      ? [{ id: "unreported" as const, label: "Not reported", heading: "Status not reported", hint: "These goals did not report a status" }]
      : []),
  ]
  const defaultTab: Tab =
    countOf("active") > 0
      ? "active"
      : (tabs.find((t) => countOf(t.id) > 0)?.id ?? "active")
  const tab: Tab = picked ?? defaultTab
  const tabInfo = tabs.find((t) => t.id === tab) ?? tabs[0]

  const departments = [
    ...new Set(
      allGoals
        .map((g) => departmentLabel(g.department))
        .filter((v): v is string => Boolean(v)),
    ),
  ].sort()

  const matchesFilters = (goal: GoalRecord) =>
    (!department || departmentLabel(goal.department) === department) &&
    `${goal.objective} ${goal.department ?? ""} ${goal.category ?? ""}`
      .toLowerCase()
      .includes(search.trim().toLowerCase())
  const sortGoals = (list: GoalRecord[]) =>
    [...list].sort((a, b) => {
      if (order === "priority") {
        const diff = priorityRank(a.priority) - priorityRank(b.priority)
        if (diff !== 0) return diff
      }
      if (order === "due") {
        const da = dueTime(a)
        const db = dueTime(b)
        if (da !== db) return da < db ? -1 : 1
      }
      return (Date.parse(b.createdAt ?? "") || 0) - (Date.parse(a.createdAt ?? "") || 0)
    })
  const filtered = sortGoals(allGoals.filter(matchesFilters))
  const visible = filtered.filter((g) => goalStatusOf(g) === tab)
  const filtersOn = Boolean(search.trim() || department)

  const refreshGoals = useCallback(() => {
    void mutate()
  }, [mutate])

  function openNew(next: GoalTemplate | null = null) {
    setEditing(null)
    setTemplate(next)
    setWizardOpen(true)
  }
  function openContinue(goal: GoalRecord) {
    setTemplate(null)
    setEditing(goal)
    setWizardOpen(true)
  }
  async function setGoalStatus(goal: GoalRecord, status: GoalStatus) {
    const response = await apiFetch(`/api/goals/${goal.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    })
    if (!response.ok) throw new Error("Could not update this goal. Try again.")
    toast.success(
      status === "paused"
        ? "Goal paused"
        : status === "active"
          ? "Goal resumed"
          : status === "completed"
            ? "Goal marked completed"
            : status === "cancelled"
              ? "Goal cancelled"
              : "Goal reopened as a draft",
    )
    await mutate()
  }

  return (
    <AppShell>
      <WsPage>
        <section className="gv-goals-hero">
          <div className="gv-rise">
            <div className="gv-eyebrow">Outcomes · Plans · Approval gates</div>
            <h1 className="gv-h1">Goals</h1>
            <p className="gv-lede" style={{ maxWidth: 540 }}>
              Say the outcome you want. Gravitre drafts a plan, links the agents
              and workflows that can deliver it, and pauses for you before
              anything executes.
            </p>
            <div className="gv-goals-actions">
              <button type="button" className="gv-btn primary" onClick={() => openNew()}>
                <Plus className="size-[18px]" aria-hidden />
                New goal
              </button>
              <a className="gv-btn outline" href="#templates">
                Browse goal templates
              </a>
              <button
                type="button"
                className="gv-iconbtn"
                aria-label="Refresh goals"
                disabled={isValidating}
                onClick={refreshGoals}
              >
                <RefreshCw className={cn("size-[18px]", isValidating && "animate-spin motion-reduce:animate-none")} />
              </button>
            </div>
          </div>
          <div className="gv-rise gv-hide-sm" style={{ animationDelay: "120ms" }}>
            <div className="gv-card gv-goals-art">
              {/* eslint-disable-next-line @next/next/no-img-element -- static SVG scene */}
              <img src="/illustrations/header-goals-office.svg" alt="" data-illustration="header-goals-office" />
            </div>
          </div>
        </section>

        <nav aria-label="Goal status" className="gv-card gv-gtabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              className={cn("gv-gtab", tab === t.id && "on")}
              aria-pressed={tab === t.id}
              onClick={() => {
                setPicked(t.id)
                setView("list")
              }}
            >
              <span className="count">{data ? countOf(t.id) : "–"}</span>
              <span className="lbl">
                <span className="gv-sdot" data-status={t.id} aria-hidden />
                {t.label}
              </span>
            </button>
          ))}
        </nav>

        <div className="gv-goals-toolbar">
          <label className="gv-field" style={{ flex: "1 1 360px" }}>
            <Search className="size-[18px]" aria-hidden />
            <input
              aria-label="Search goals"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search objectives, categories or departments"
            />
          </label>
          <label className="gv-field" style={{ flex: "0 1 220px" }}>
            <span>Department</span>
            <select
              aria-label="Goal department"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            >
              <option value="">All</option>
              {departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <label className="gv-field" style={{ flex: "0 1 200px" }}>
            <span>Sort</span>
            <select
              aria-label="Sort goals"
              value={order}
              onChange={(e) => setOrder(e.target.value as Sort)}
            >
              <option value="recent">Newest first</option>
              <option value="due">Due soonest</option>
              <option value="priority">Priority</option>
            </select>
          </label>
          <div className="gv-viewtoggle" role="group" aria-label="View">
            <button
              type="button"
              className={cn("gv-iconbtn bare", view === "list" && "on")}
              aria-label="List view"
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
            >
              <LayoutList className="size-[18px]" />
            </button>
            <button
              type="button"
              className={cn("gv-iconbtn bare", view === "board" && "on")}
              aria-label="Board view"
              aria-pressed={view === "board"}
              onClick={() => setView("board")}
            >
              <SquareKanban className="size-[18px]" />
            </button>
          </div>
        </div>

        {error ? (
          <div className="gv-card gv-goals-alert" role="alert">
            <span style={{ flex: "1 1 auto" }}>
              Could not load goals.{" "}
              {data ? "Your last loaded goals remain available." : "Try again to refresh the list."}
            </span>
            <button type="button" className="gv-btn outline sm" onClick={refreshGoals}>
              Try again
            </button>
          </div>
        ) : null}

        <div className="gv-goals-cols">
          <div className="gv-goals-main">
            {isLoading && !data ? (
              <div className="gv-card gv-goal" aria-busy="true" aria-label="Loading goals">
                <div className="gv-skel" style={{ width: "30%" }} />
                <div className="gv-skel" style={{ width: "70%", height: 18, marginTop: 16 }} />
                <div className="gv-skel" style={{ width: "100%", height: 90, marginTop: 22, borderRadius: 12 }} />
              </div>
            ) : !data ? null : allGoals.length === 0 ? (
              <div className="gv-card gv-goals-empty">
                {/* eslint-disable-next-line @next/next/no-img-element -- static SVG scene */}
                <img src="/illustrations/moment-milestone.svg" alt="" data-illustration="moment-milestone" />
                <div style={{ flex: "1 1 260px" }}>
                  <h2 className="gv-h2">No goals yet</h2>
                  <p style={{ margin: "8px 0 0", color: "var(--gv-muted)", fontSize: 14, lineHeight: 1.5 }}>
                    A goal states the outcome you want. Gravitre drafts a plan tied to
                    your connectors and approval gates, agents carry out the work, and
                    results are measured against the goal.
                  </p>
                  <button type="button" className="gv-btn primary" style={{ marginTop: 16 }} onClick={() => openNew()}>
                    <Plus className="size-[18px]" aria-hidden />
                    Create your first goal
                  </button>
                </div>
              </div>
            ) : view === "board" ? (
              <div className="gv-board" aria-label="Goals board">
                {tabs.map((t) => {
                  const column = filtered.filter((g) => goalStatusOf(g) === t.id)
                  return (
                    <section key={t.id} className="gv-board-col" aria-label={t.label}>
                      <h3>
                        <span className="gv-sdot" data-status={t.id} aria-hidden />
                        {t.label}
                        <span className="n">{column.length}</span>
                      </h3>
                      {column.length ? (
                        column.map((g) => <GoalBoardCard key={g.id} goal={g} />)
                      ) : (
                        <div className="gv-board-empty">None</div>
                      )}
                    </section>
                  )
                })}
              </div>
            ) : (
              <>
                <div className="gv-goals-sechead">
                  <h2>
                    {tabInfo.heading}
                    <span className="n">{visible.length}</span>
                  </h2>
                  <span className="gv-hint">{tabInfo.hint}</span>
                </div>
                {visible.length === 0 ? (
                  <div className="gv-empty">
                    {filtersOn ? (
                      <>
                        No {tabInfo.label.toLowerCase()} goals match these filters.{" "}
                        <button
                          type="button"
                          className="gv-btn plain sm"
                          onClick={() => {
                            setSearch("")
                            setDepartment("")
                          }}
                        >
                          Clear filters
                        </button>
                      </>
                    ) : (
                      `No ${tabInfo.label.toLowerCase()} goals right now.`
                    )}
                  </div>
                ) : (
                  visible.map((goal) => (
                    <GoalCard
                      key={goal.id}
                      goal={goal}
                      related={
                        assignments && goalStatusOf(goal) !== "completed" && goalStatusOf(goal) !== "cancelled"
                          ? findRelatedAssignment(goal, assignments)
                          : null
                      }
                      onContinue={openContinue}
                      onSetStatus={setGoalStatus}
                    />
                  ))
                )}
                <div className="gv-goals-placeholders">
                  {tab !== "active" && countOf("active") === 0 ? (
                    <div className="gv-card gv-goals-ph">
                      <span className="gv-sdot" data-status="active" aria-hidden />
                      <div>
                        <strong style={{ fontWeight: 600 }}>In motion</strong>
                        <div>Approve a plan to start your first goal</div>
                      </div>
                    </div>
                  ) : null}
                  {tab !== "completed" && countOf("completed") === 0 ? (
                    <div className="gv-card gv-goals-ph">
                      <span className="gv-sdot" data-status="completed" aria-hidden />
                      <div>
                        <strong style={{ fontWeight: 600 }}>Completed</strong>
                        <div>Finished goals and their results land here</div>
                      </div>
                    </div>
                  ) : null}
                </div>
              </>
            )}

            <section id="templates" style={{ marginTop: 20, scrollMarginTop: 24 }}>
              <div className="gv-goals-sechead" style={{ marginBottom: 14 }}>
                <h2>Start from a goal template</h2>
                <Link className="gv-link" href="/marketplace/assets">
                  See all in Explore →
                </Link>
              </div>
              <div className="gv-tpl-grid">
                {GOAL_TEMPLATES.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className="gv-card gv-tpl"
                    onClick={() => openNew(t)}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element -- static SVG scene */}
                    <img src={`/illustrations/${t.illustration}.svg`} alt="" data-illustration={t.illustration} />
                    <div className="cap">
                      <div className="k">{departmentLabel(t.department)}</div>
                      <div className="t">{t.objective}</div>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          </div>

          <aside className="gv-goals-aside">
            <div className="gv-card" style={{ padding: "20px 22px" }}>
              <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>How a goal runs</h2>
              <ol className="gv-howto">
                {HOW_IT_RUNS.map((s, i) => (
                  <li key={s.t}>
                    <span className={cn("num", i === 0 && "first")}>{i + 1}</span>
                    <div>
                      <div className="t">{s.t}</div>
                      <div className="d">{s.d}</div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
            <div className="gv-card" style={{ padding: "18px 20px" }}>
              <div className="gv-eyebrow">Health key</div>
              <div className="gv-health">
                <span>
                  <span className="gv-pill brand">On track</span>
                  <span className="d">Pace meets the target</span>
                </span>
                <span>
                  <span className="gv-pill amber">At risk</span>
                  <span className="d">Behind pace or blocked</span>
                </span>
                <span>
                  <span className="gv-pill offtrack">Off track</span>
                  <span className="d">Will miss without action</span>
                </span>
              </div>
            </div>
          </aside>
        </div>
      </WsPage>

      <GoalWorkflowWizard
        open={wizardOpen}
        onOpenChange={(next) => {
          setWizardOpen(next)
          if (!next) {
            setEditing(null)
            setTemplate(null)
          }
        }}
        onGoalSaved={refreshGoals}
        initialGoal={editing}
        template={template}
      />
    </AppShell>
  )
}
