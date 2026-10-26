"use client"

// Agents > Roster > Team ("Meet your crew"), from the AI Team design (2026-10-26).
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMemo, useRef, useState, type FormEvent, type ReactNode } from "react"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import {
  AUTONOMY_STEPS,
  ROSTER_DEPARTMENTS,
  blockedReason,
  emptyDepartments,
  formatRate,
  matchesAgentSearch,
  needsYou,
  pickAgentForJob,
  standoutAgent,
  teamJobIdeas,
  type DepartmentMeta,
  type RosterAgent,
} from "@/lib/agents-roster"
import { DEPARTMENT_ICONS } from "@/lib/department-icons"
import { cn } from "@/lib/utils"
import { AppChips, agentChatHref, agentHref, giveTaskHref, newAgentHref } from "./agent-bits"

const DEPARTMENT_ORDER = new Map(ROSTER_DEPARTMENTS.map((d, i) => [d.id, i]))

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
}

function list(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ""
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

export function marketplaceAgentsHref(department?: AgentDepartmentId): string {
  const params = new URLSearchParams({ type: "ai_agent" })
  if (department) params.set("department", department)
  return `/marketplace/assets?${params.toString()}`
}

/** Assignment flow with the brief filled in; with an agent it is preselected, otherwise the flow picks its default. */
export function handOffHref(task: string, agentId?: string | null): string {
  const params = new URLSearchParams()
  if (agentId) params.set("agent", agentId)
  params.set("task", task)
  return `/assignments/new?${params.toString()}`
}

function DeptIcon({ department, size }: { department: AgentDepartmentId; size: number }) {
  const Icon = DEPARTMENT_ICONS[department] ?? DEPARTMENT_ICONS.general
  return <Icon size={size} strokeWidth={2} aria-hidden />
}

function ArrowIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  )
}

function statusPill(agent: RosterAgent): { label: string; tone: "ok" | "busy" | "warn" | "off" } {
  switch (agent.state) {
    case "working":
      return { label: "Working", tone: "busy" }
    case "blocked":
      return { label: "Needs you", tone: "warn" }
    case "not_set_up":
      return { label: "Not set up", tone: "off" }
    default:
      return { label: "Ready", tone: "ok" }
  }
}

function Stats({
  agents,
  statsAvailable,
  pendingApprovals,
}: {
  agents: RosterAgent[]
  statsAvailable: boolean
  pendingApprovals: number | null
}) {
  const working = agents.filter((a) => a.state === "working").length
  const available = agents.filter((a) => a.state !== "blocked" && a.state !== "not_set_up").length
  const tasksToday = agents.reduce((sum, a) => sum + a.tasksToday, 0)
  const failedToday = agents.reduce((sum, a) => sum + (a.stats?.failedToday ?? 0), 0)
  const rate = tasksToday + failedToday > 0 ? formatRate((tasksToday / (tasksToday + failedToday)) * 100) : null
  const covered = new Set(agents.map((a) => a.department))
  const missing = ROSTER_DEPARTMENTS.filter((d) => !covered.has(d.id))
  const blocked = needsYou(agents)
  const approvals = pendingApprovals ?? 0
  const needs = blocked.length + approvals
  const needsHref =
    approvals > 0 ? "/approvals" : blocked.length === 1 ? agentHref(blocked[0].id) : "/agents?view=list&status=needs"
  const needsParts = [
    approvals > 0 ? plural(approvals, "approval") : null,
    blocked.length > 0 ? `${plural(blocked.length, "agent")} stuck` : null,
  ].filter(Boolean)

  const coverageLabel =
    missing.length === 0
      ? "Coverage: every department has an agent"
      : `Coverage: ${missing.length === ROSTER_DEPARTMENTS.length ? "no department has" : `every department but ${list(missing.map((d) => d.name))} has`} an agent`

  const needsBody = (
    <>
      <span className="k">Needs you</span>
      <span className="v">
        {needs} {needs === 0 ? <small>All clear</small> : <small>Review →</small>}
      </span>
      <span className="s">{needs === 0 ? "Approvals and stuck tasks show up here" : needsParts.join(" · ")}</span>
    </>
  )

  return (
    <div className="tm-stats">
      <div className="tm-stat ok">
        <span className="k">
          <span className="tm-live" aria-hidden />
          Available
        </span>
        <span className="v">{available}</span>
        <span className="s">{working > 0 ? `${working} working now` : "Nobody is mid task"}</span>
      </div>
      <div className="tm-stat">
        <span className="k">Tasks done today</span>
        {statsAvailable ? (
          <>
            <span className="v">{tasksToday}</span>
            <span className="s">
              {tasksToday > 0
                ? rate
                  ? `${rate} finished without a hitch`
                  : "Finished today"
                : working > 0
                  ? "First one is on the way"
                  : "Nothing finished yet"}
            </span>
          </>
        ) : (
          <>
            <span className="v">
              <small>Not reported</small>
            </span>
            <span className="s">Activity is loading or unavailable</span>
          </>
        )}
      </div>
      <div className="tm-stat">
        <span className="k">Departments</span>
        <span className="v">
          {covered.size} <small>of {ROSTER_DEPARTMENTS.length}</small>
        </span>
        <span className="tm-cover" role="img" aria-label={coverageLabel}>
          {ROSTER_DEPARTMENTS.map((d) => (
            <span key={d.id} className={cn(`rs-d-${d.id}`, covered.has(d.id) && "on")} />
          ))}
        </span>
      </div>
      {needs > 0 ? (
        <Link className="tm-stat warn" href={needsHref}>
          {needsBody}
        </Link>
      ) : (
        <div className="tm-stat">{needsBody}</div>
      )}
    </div>
  )
}

function Standout({ star, starter }: { star: RosterAgent | null; starter: RosterAgent | null }) {
  if (star) {
    const rate = formatRate(star.successToday)
    return (
      <aside className="tm-standout" aria-label="Today's standout">
        <span className={cn("tm-standout-ic", `rs-d-${star.department}`)} aria-hidden>
          <span className="ring" />
          <span className="face">
            <DeptIcon department={star.department} size={28} />
          </span>
        </span>
        <div className="body">
          <span className="eb">Today&apos;s standout</span>
          <span className="nm">{star.name}</span>
          <span className="sub">
            {plural(star.tasksToday, "task")} done today{rate ? `, ${rate} without a hitch` : ""}.
          </span>
        </div>
        <Link className="tm-standout-btn" href={agentHref(star.id)}>
          See its work
        </Link>
      </aside>
    )
  }
  return (
    <aside className="tm-standout" aria-label="Today's standout">
      <span className="tm-standout-ic" aria-hidden>
        <span className="ring" />
        <span className="face">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 8h1a4 4 0 1 1 0 8h-1" />
            <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z" />
            <path className="tm-blink" d="M6 2v2M10 2v2M14 2v2" />
          </svg>
        </span>
      </span>
      <div className="body">
        <span className="eb">Today&apos;s standout</span>
        <span className="nm">Your team is warming up</span>
        <span className="sub">The first task an agent completes will be featured here.</span>
      </div>
      <Link className="tm-standout-btn" href={starter ? giveTaskHref(starter.id) : newAgentHref()}>
        Give a task
      </Link>
    </aside>
  )
}

function HandOff({ agents, gated }: { agents: RosterAgent[]; gated: boolean }) {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const [job, setJob] = useState("")
  const [ideaDept, setIdeaDept] = useState<AgentDepartmentId | null>(null)
  const ideas = useMemo(() => teamJobIdeas(agents), [agents])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const task = job.trim()
    if (!task) {
      inputRef.current?.focus()
      return
    }
    const agent = pickAgentForJob(task, agents, ideaDept)
    router.push(handOffHref(task, agent?.id))
  }

  return (
    <section aria-label="Hand off a job" className="tm-handoff">
      <form onSubmit={submit}>
        <label className="tm-job">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--gv-brand)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
            <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" />
          </svg>
          <span className="sr-only">Describe a job for your team</span>
          <input
            ref={inputRef}
            type="text"
            value={job}
            maxLength={12000}
            onChange={(e) => {
              setJob(e.target.value)
              if (!e.target.value.trim()) setIdeaDept(null)
            }}
            placeholder="Describe a job in plain words. Gravitre picks the right agent."
          />
        </label>
        {gated ? (
          <span className="tm-lock">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <rect x="5" y="11" width="14" height="10" rx="2" />
              <path d="M8 11V7a4 4 0 0 1 8 0v4" />
            </svg>
            Writes wait for your OK
          </span>
        ) : null}
        <button type="submit" className="tm-go">
          Hand it off
          <ArrowIcon />
        </button>
      </form>
      {ideas.length > 0 ? (
        <div className="tm-ideas">
          <span className="eb">Try</span>
          {ideas.map((idea) => (
            <button
              key={idea.department}
              type="button"
              className="tm-idea"
              onClick={() => {
                setJob(idea.text)
                setIdeaDept(idea.department)
                inputRef.current?.focus()
              }}
            >
              <span className={cn("dot", `rs-d-${idea.department}`)} aria-hidden>
                <DeptIcon department={idea.department} size={13} />
              </span>
              {idea.text}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function AgentCard({ agent }: { agent: RosterAgent }) {
  const pill = statusPill(agent)
  const reason = blockedReason(agent)
  const live = agent.state === "ready" || agent.state === "active_today"
  const step = agent.autonomy ? AUTONOMY_STEPS[agent.autonomy] : null
  return (
    <article className={cn("tm-card", `rs-d-${agent.department}`)}>
      <div className="tm-card-head">
        <span className="tm-ava" aria-hidden>
          {live ? <span className="ring" /> : null}
          <span className="face">
            <DeptIcon department={agent.department} size={20} />
          </span>
        </span>
        <div className="who">
          <Link className="nm" href={agentHref(agent.id)}>
            {agent.name}
          </Link>
          <span className="dept">{agent.role || agent.departmentLabel}</span>
        </div>
        <span className={cn("tm-pill", pill.tone)}>
          <span className="d" aria-hidden />
          {pill.label}
        </span>
      </div>

      {agent.description ? (
        <p className="tm-blurb">{agent.description}</p>
      ) : (
        <p className="tm-blurb none">No instructions yet. Open it to tell it what to do.</p>
      )}

      {agent.state === "working" ? (
        <div className="tm-now">
          <span>
            <b>Now:</b>{" "}
            {agent.currentTask ?? (agent.stats && agent.stats.runningNow > 1 ? `Running ${agent.stats.runningNow} tasks` : "Running a task")}
          </span>
          <span className="bar" aria-hidden>
            <span className="tm-slide" />
          </span>
        </div>
      ) : reason ? (
        <Link className="tm-now warn" href={agentHref(agent.id)}>
          <span>
            <b>Needs you:</b> {reason}
          </span>
        </Link>
      ) : null}

      <div className="tm-meta">
        {agent.apps.length > 0 ? (
          <div className="tm-works">
            <span className="lbl">Works in</span>
            <AppChips apps={agent.apps} max={3} />
          </div>
        ) : (
          <div className="tm-works">
            <span className="lbl">No apps connected yet</span>
          </div>
        )}
        {step ? (
          <div className="tm-level">
            <span className="lbl">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z" />
              </svg>
              {step.label}
            </span>
            <span className="segs" role="img" aria-label={`Autonomy ${step.level} of 3: ${step.label}`}>
              {[1, 2, 3].map((n) => (
                <span key={n} className={cn(step.level >= n && "on")} />
              ))}
            </span>
          </div>
        ) : null}
      </div>

      <div className="tm-card-foot">
        <Link className="tm-task" href={giveTaskHref(agent.id)} aria-label={`Give ${agent.name} a task`}>
          Give a task
        </Link>
        <Link className="tm-chat" href={agentChatHref(agent.id)} aria-label={`Chat with ${agent.name}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </Link>
      </div>
    </article>
  )
}

function HireCard({ missing }: { missing: DepartmentMeta[] }) {
  const one = missing.length === 1 ? missing[0] : null
  return (
    <article className={cn("tm-hire", one && `rs-d-${one.id}`)}>
      <span className="tm-ava" aria-hidden>
        <span className="face">
          {one ? (
            <DeptIcon department={one.id} size={20} />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
          )}
        </span>
      </span>
      <span className="nm">
        {one ? `${one.name} has no agent yet` : `${missing.length} departments have no agent yet`}
      </span>
      <span className="sub">
        {one
          ? `Add one from the Marketplace to cover all ${ROSTER_DEPARTMENTS.length} departments.`
          : `${list(missing.map((d) => d.name))}. Add agents from the Marketplace to cover all ${ROSTER_DEPARTMENTS.length}.`}
      </span>
      <Link className="tm-browse" href={marketplaceAgentsHref(one?.id)}>
        Browse agents
        <ArrowIcon size={14} />
      </Link>
    </article>
  )
}

export function RosterTeamView({
  agents,
  statsAvailable,
  pendingApprovals = null,
  viewNav,
}: {
  agents: RosterAgent[]
  statsAvailable: boolean
  /** Pending approvals from GET /api/approvals; null while unknown. */
  pendingApprovals?: number | null
  /** Team / List / Graph switcher, shown beside the heading. */
  viewNav?: ReactNode
}) {
  const [dept, setDept] = useState<AgentDepartmentId | "all">("all")
  const [query, setQuery] = useState("")
  const sorted = useMemo(
    () =>
      [...agents].sort(
        (x, y) =>
          (DEPARTMENT_ORDER.get(x.department) ?? 99) - (DEPARTMENT_ORDER.get(y.department) ?? 99) ||
          x.name.localeCompare(y.name),
      ),
    [agents],
  )
  const star = useMemo(() => standoutAgent(agents), [agents])
  const empty = useMemo(() => emptyDepartments(agents), [agents])
  const covered = ROSTER_DEPARTMENTS.length - empty.length
  const anyGated = agents.some((a) => a.gated)
  const starter = agents.find((a) => a.state === "ready") ?? agents.find((a) => a.state !== "not_set_up") ?? null

  const shown = sorted.filter((a) => (dept === "all" || a.department === dept) && matchesAgentSearch(a, query))
  const missing = query.trim() ? [] : dept === "all" ? empty : empty.filter((d) => d.id === dept)

  return (
    <div className="tm">
      <section className="tm-head">
        <div className="tm-title">
          <span className="eb">Your AI workforce</span>
          <h1>{plural(agents.length, "agent")}, ready when you are.</h1>
          <p>
            Spread across {plural(covered, "department")}. Hand any of them a job and it starts right away.
            {anyGated ? " Anything that writes to your apps waits for your OK." : ""}
          </p>
        </div>
        {viewNav}
      </section>

      <section className="tm-top">
        <Stats agents={agents} statsAvailable={statsAvailable} pendingApprovals={pendingApprovals} />
        <Standout star={star} starter={starter} />
      </section>

      <HandOff agents={agents} gated={anyGated} />

      <section id="crew" className="tm-crew" aria-label="Your agents">
        <div className="tm-crew-bar">
          <div role="group" aria-label="Filter by department" className="tm-chips">
            <button type="button" className={cn("tm-chip", dept === "all" && "on")} aria-pressed={dept === "all"} onClick={() => setDept("all")}>
              <span className="tm-all" aria-hidden />
              All <span className="n">{agents.length}</span>
            </button>
            {ROSTER_DEPARTMENTS.map((d) => (
              <button
                key={d.id}
                type="button"
                className={cn("tm-chip", `rs-d-${d.id}`, dept === d.id && "on")}
                aria-pressed={dept === d.id}
                onClick={() => setDept(d.id)}
              >
                <span className="ic">
                  <DeptIcon department={d.id} size={16} />
                </span>
                {d.name} <span className="n">{agents.filter((a) => a.department === d.id).length}</span>
              </button>
            ))}
          </div>
          <label className="tm-find">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find an agent" aria-label="Find an agent" />
          </label>
        </div>

        <div className="tm-grid">
          {shown.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
          {missing.length > 0 ? <HireCard missing={missing} /> : null}
        </div>
        {shown.length === 0 && missing.length === 0 ? (
          <p className="tm-none">
            {query.trim() ? `No agents match “${query.trim()}”.` : "No agents in this department yet."}
          </p>
        ) : null}
      </section>
    </div>
  )
}
