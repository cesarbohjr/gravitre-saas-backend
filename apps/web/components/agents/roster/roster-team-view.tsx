"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import {
  ROSTER_DEPARTMENTS,
  blockedReason,
  emptyDepartments,
  formatRate,
  groupByDepartment,
  needsYou,
  standoutAgent,
  yesterdayBestAgent,
  type DepartmentGroup,
  type RosterAgent,
} from "@/lib/agents-roster"
import { cn } from "@/lib/utils"
import { DepartmentGlyph, DepartmentIcon } from "@/components/agents/department-icon"
import {
  AgentAvatar,
  AppChips,
  GiveTaskLink,
  WarnIcon,
  agentHref,
  giveTaskHref,
  newAgentHref,
} from "./agent-bits"

/** Agents shown per department band; the rest are one click away in the list view. */
export const TEAM_BAND_LIMIT = 4
const SPARK_DAYS = 9

export function departmentListHref(dept: AgentDepartmentId): string {
  return `/agents?view=list&dept=${encodeURIComponent(dept)}`
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
}

function statusLine(agent: RosterAgent): string {
  switch (agent.state) {
    case "working":
      return "Working now"
    case "blocked":
      return "Needs you"
    case "active_today":
      return agent.tasksToday >= 5 ? "Busy day" : "Active today"
    case "not_set_up":
      return "Not set up yet"
    default:
      return "Ready for work"
  }
}

function AgentCard({ agent, star }: { agent: RosterAgent; star: boolean }) {
  const reason = blockedReason(agent)
  const rate = formatRate(agent.successToday)
  return (
    <article className={cn("rs-ag", star && "star")}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <AgentAvatar agent={agent} />
        <div style={{ flex: "1 1 auto", minWidth: 0 }}>
          <Link className="nm" href={agentHref(agent.id)}>
            {agent.name}
          </Link>
          {agent.role ? <div className="role">{agent.role}</div> : null}
        </div>
      </div>
      {agent.description ? (
        <p className="does">{agent.description}</p>
      ) : (
        <p className="does none">No instructions yet. Open it to tell it what to do.</p>
      )}
      {reason ? (
        <Link className="rs-flag" href={agentHref(agent.id)}>
          <WarnIcon />
          {reason}
        </Link>
      ) : null}
      {agent.tasksToday > 0 ? (
        <div className="rs-good">
          {plural(agent.tasksToday, "task")} done today{rate ? ` · ${rate} success` : ""}
        </div>
      ) : null}
      <AppChips apps={agent.apps} />
      <div className="rs-ag-foot">
        <span className="st">{statusLine(agent)}</span>
        <GiveTaskLink agent={agent} />
      </div>
    </article>
  )
}

function DepartmentBand({ group, starId }: { group: DepartmentGroup; starId: string | null }) {
  const { meta, agents } = group
  const lead = agents.find((a) => a.state !== "blocked" && a.state !== "not_set_up") ?? agents[0]
  const shown = agents.slice(0, TEAM_BAND_LIMIT)
  const hidden = agents.length - shown.length
  return (
    <section className={cn("gv-card gv-rise rs-band", `rs-d-${meta.id}`)} aria-labelledby={`dept-${meta.id}`}>
      <div className="rs-band-side">
        {meta.illustration ? (
          <div className="rs-band-art">
            {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
            <img src={`/illustrations/${meta.illustration}.svg`} alt={meta.alt} width={320} height={260} decoding="async" />
          </div>
        ) : null}
        <div className="rs-band-copy">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <DepartmentIcon department={meta.id} size="sm" />
            <h2 id={`dept-${meta.id}`}>{meta.name}</h2>
            <span className="rs-cnt">{agents.length}</span>
          </div>
          <p>{meta.blurb}</p>
          <Link className="gv-btn outline rs-band-job" href={giveTaskHref(lead.id)}>
            Give {meta.name} a job
          </Link>
        </div>
      </div>
      <div className="rs-band-main">
        <div className="rs-band-grid">
          {shown.map((agent) => (
            <AgentCard key={agent.id} agent={agent} star={agent.id === starId} />
          ))}
        </div>
        {hidden > 0 ? (
          <div className="rs-band-more">
            <span>
              Showing {shown.length} of {agents.length} {meta.name} agents
            </span>
            <Link className="gv-btn outline rs-viewall" href={departmentListHref(meta.id)}>
              View all {agents.length} in list view
              <ArrowIcon />
            </Link>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  )
}

/** Shown when nobody has finished a task today (v2 "warming up" card). */
function WarmingUp({
  starter,
  yesterday,
}: {
  starter: RosterAgent | null
  /** Busiest agent yesterday; the "See yesterday's best" button only appears when there is one. */
  yesterday: { agent: RosterAgent; tasks: number } | null
}) {
  const [showYesterday, setShowYesterday] = useState(false)
  if (showYesterday && yesterday) {
    const { agent, tasks } = yesterday
    return (
      <aside className="rs-standout" aria-labelledby="standout-heading">
        <span className="eb">Yesterday&apos;s best</span>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <AgentAvatar agent={agent} />
          <div style={{ minWidth: 0 }}>
            <h2 id="standout-heading" className="nm">
              {agent.name}
            </h2>
            <div className="sub">{agent.role || agent.departmentLabel}</div>
          </div>
        </div>
        <div>
          <div className="num">{tasks}</div>
          <div className="lbl">{tasks === 1 ? "task" : "tasks"} finished yesterday</div>
        </div>
        <div className="rs-standout-actions">
          <Link className="rs-sbtn primary" href={giveTaskHref(agent.id)}>
            Give it today&apos;s first task
          </Link>
          <button type="button" className="rs-sbtn" onClick={() => setShowYesterday(false)}>
            Back to today
          </button>
        </div>
      </aside>
    )
  }
  return (
    <aside className="rs-standout" aria-labelledby="standout-heading">
      <span className="eb">Today&apos;s standout</span>
      <div className="rs-standout-art">
        {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
        <img src="/illustrations/roster-standout.svg" alt="" width={320} height={260} decoding="async" />
      </div>
      <h2 id="standout-heading" className="nm">
        Your team is warming up
      </h2>
      <p className="sub">Nothing finished yet today. The first task an agent completes will be featured right here.</p>
      <div className="rs-standout-actions">
        <Link className="rs-sbtn primary" href={starter ? giveTaskHref(starter.id) : newAgentHref()}>
          Give a task
        </Link>
        {yesterday ? (
          <button type="button" className="rs-sbtn" onClick={() => setShowYesterday(true)}>
            See yesterday&apos;s best
          </button>
        ) : null}
      </div>
    </aside>
  )
}

function Standout({
  agent,
  days,
  yesterday,
  starter,
}: {
  agent: RosterAgent | null
  days: number
  yesterday: { agent: RosterAgent; tasks: number } | null
  /** Agent to hand a first task to when nothing has run yet. */
  starter: RosterAgent | null
}) {
  if (!agent) return <WarmingUp starter={starter} yesterday={yesterday} />
  const daily = agent.stats?.daily ?? []
  const recent = daily.slice(-Math.min(SPARK_DAYS, days || SPARK_DAYS))
  const peak = Math.max(1, ...recent)
  const streak = recent.length >= 3 && recent.slice(-3).every((n) => n > 0)
  const rate = formatRate(agent.successToday)
  return (
    <aside className="rs-standout" aria-label="Today's standout">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="eb">Today&apos;s standout</span>
        {streak ? <span className="gv-pill">On a streak</span> : null}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <AgentAvatar agent={agent} />
        <div style={{ minWidth: 0 }}>
          <div className="nm">{agent.name}</div>
          <div className="sub">{[agent.role || agent.departmentLabel, agent.model !== "default" ? agent.model : null].filter(Boolean).join(" · ")}</div>
        </div>
      </div>
      <div
        className="rs-spark"
        role="img"
        aria-label={`Tasks completed over the last ${recent.length} days: ${recent.join(", ")}`}
      >
        {recent.map((n, i) => (
          <span
            key={i}
            className={cn(n === 0 && "zero", i === recent.length - 1 && "today")}
            style={{ height: `${Math.max(5, Math.round((n / peak) * 100))}%`, animationDelay: `${i * 60}ms` }}
          />
        ))}
      </div>
      <div style={{ display: "flex", gap: 24 }}>
        <div>
          <div className="num">{agent.tasksToday}</div>
          <div className="lbl">tasks today</div>
        </div>
        <div>
          <div className="num">{rate ?? "Not reported"}</div>
          <div className="lbl">success</div>
        </div>
      </div>
      <Link href={agentHref(agent.id)}>See its work →</Link>
    </aside>
  )
}

export function RosterTeamView({
  agents,
  statsAvailable,
  days,
}: {
  agents: RosterAgent[]
  statsAvailable: boolean
  days: number
}) {
  const [dept, setDept] = useState<AgentDepartmentId | "all">("all")
  const groups = useMemo(() => groupByDepartment(agents), [agents])
  const empty = useMemo(() => emptyDepartments(agents), [agents])
  const star = useMemo(() => standoutAgent(agents), [agents])
  const yesterday = useMemo(() => (star ? null : yesterdayBestAgent(agents)), [agents, star])
  const blocked = useMemo(() => needsYou(agents), [agents])
  const available = agents.filter((a) => a.state !== "blocked" && a.state !== "not_set_up").length
  const tasksToday = agents.reduce((sum, a) => sum + a.tasksToday, 0)
  const anyGated = agents.some((a) => a.gated)
  const covered = groups.length

  const bands = dept === "all" ? groups : groups.filter((g) => g.meta.id === dept)
  const starter = agents.find((a) => a.state === "ready") ?? agents.find((a) => a.state !== "not_set_up") ?? null
  const showEmpty = dept === "all" ? empty : empty.filter((d) => d.id === dept)

  const needsHref = blocked.length === 1 ? agentHref(blocked[0].id) : "/agents?view=list&status=needs"
  const needsHint = blocked.length === 1 ? blockedReason(blocked[0]) : blocked.length > 1 ? "See who" : null

  return (
    <>
      <section className="gv-rise rs-hero">
        <div className="gv-card rs-hero-main">
          <div>
            <div className="gv-eyebrow">Your AI workforce</div>
            <h1>
              {plural(agents.length, "agent")}, ready when you are.
            </h1>
            <p className="lede">
              Spread across {plural(covered, "department")}. Hand any of them a job and it starts right away.
              {anyGated ? " Anything that writes to your apps waits for your OK." : ""}
            </p>
          </div>
          <div className="rs-stats">
            <div className="rs-stat ok">
              <div className="k">
                <span className="gv-ping" style={{ width: 8, height: 8, background: "var(--gv-accent)" }} />
                Available
              </div>
              <div className="v">{available}</div>
            </div>
            <div className="rs-stat">
              <div className="k">Tasks done today</div>
              <div className="v">{statsAvailable ? tasksToday : <small>Not reported</small>}</div>
            </div>
            <div className="rs-stat">
              <div className="k">Departments covered</div>
              <div className="v">
                {covered} <small>of {ROSTER_DEPARTMENTS.length}</small>
              </div>
            </div>
            {blocked.length > 0 ? (
              <Link className="rs-stat warn" href={needsHref}>
                <div className="k">Needs you</div>
                <div className="v">
                  {blocked.length} {needsHint ? <small>{needsHint.length > 28 ? "Review" : needsHint} →</small> : null}
                </div>
              </Link>
            ) : (
              <div className="rs-stat">
                <div className="k">Needs you</div>
                <div className="v">
                  0 <small>All clear</small>
                </div>
              </div>
            )}
          </div>
        </div>
        <Standout agent={star} days={days} yesterday={statsAvailable ? yesterday : null} starter={starter} />
      </section>

      <div className="rs-chips" role="group" aria-label="Filter by department" style={{ marginTop: 28 }}>
        <button
          type="button"
          className={cn("gv-fchip", dept === "all" && "on")}
          aria-pressed={dept === "all"}
          onClick={() => setDept("all")}
        >
          <span className="rs-ddot" />
          All <b>{agents.length}</b>
        </button>
        {groups.map((g) => (
          <button
            key={g.meta.id}
            type="button"
            className={cn("gv-fchip", `rs-d-${g.meta.id}`, dept === g.meta.id && "on")}
            aria-pressed={dept === g.meta.id}
            onClick={() => setDept(g.meta.id)}
          >
            <DepartmentGlyph department={g.meta.id} size={13} />
            {g.meta.name} <b>{g.agents.length}</b>
          </button>
        ))}
      </div>

      {bands.map((group) => (
        <DepartmentBand key={group.meta.id} group={group} starId={star?.id ?? null} />
      ))}

      {showEmpty.length > 0 ? (
        <section className="rs-rest" aria-label="Departments without agents">
          <h2>Open seats</h2>
          <div className="rs-rest-grid">
            {showEmpty.map((meta) => (
              <div key={meta.id} className={cn("rs-emptydept", `rs-d-${meta.id}`)}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <DepartmentIcon department={meta.id} size="xs" />
                  <strong style={{ fontWeight: 600 }}>{meta.name}</strong>
                  <span className="rs-cnt" style={{ marginLeft: "auto" }}>
                    0
                  </span>
                </div>
                <p>{meta.emptyHint}</p>
                <Link className="gv-link" href={newAgentHref(meta.name)}>
                  + Hire {/^[aeiou]/i.test(meta.name) ? "an" : "a"} {meta.name.toLowerCase()} agent
                </Link>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  )
}
