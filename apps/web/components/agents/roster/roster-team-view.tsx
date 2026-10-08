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
  type DepartmentGroup,
  type RosterAgent,
} from "@/lib/agents-roster"
import { cn } from "@/lib/utils"
import {
  AgentAvatar,
  AppChips,
  GiveTaskLink,
  WarnIcon,
  agentHref,
  giveTaskHref,
  newAgentHref,
} from "./agent-bits"

const BAND_COUNT = 3
const SPARK_DAYS = 9

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
  return (
    <section className={cn("gv-card gv-rise rs-band", `rs-d-${meta.id}`)} aria-labelledby={`dept-${meta.id}`}>
      <div className="rs-band-side">
        {meta.illustration ? (
          // eslint-disable-next-line @next/next/no-img-element -- static library scene
          <img src={`/illustrations/${meta.illustration}.svg`} alt={meta.alt} width={420} height={260} loading="lazy" />
        ) : null}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="rs-dsq" />
            <h2 id={`dept-${meta.id}`}>{meta.name}</h2>
            <span className="rs-cnt">{agents.length}</span>
          </div>
          <p>{meta.blurb}</p>
        </div>
        <Link className="gv-btn outline sm" href={giveTaskHref(lead.id)} style={{ alignSelf: "flex-start" }}>
          Give {meta.name} a job
        </Link>
      </div>
      <div className="rs-band-grid">
        {agents.map((agent) => (
          <AgentCard key={agent.id} agent={agent} star={agent.id === starId} />
        ))}
      </div>
    </section>
  )
}

function Standout({ agent, days }: { agent: RosterAgent | null; days: number }) {
  if (!agent) {
    return (
      <aside className="rs-standout quiet" aria-label="Today's standout">
        <span className="eb">Today&apos;s standout</span>
        {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
        <img src="/illustrations/moment-focus-time.svg" alt="" width={260} height={170} />
        <div className="nm">No finished tasks yet today</div>
        <div className="sub">The first agent to finish a task today shows up here.</div>
      </aside>
    )
  }
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
  const blocked = useMemo(() => needsYou(agents), [agents])
  const available = agents.filter((a) => a.state !== "blocked" && a.state !== "not_set_up").length
  const tasksToday = agents.reduce((sum, a) => sum + a.tasksToday, 0)
  const anyGated = agents.some((a) => a.gated)
  const covered = groups.length

  const visible = dept === "all" ? groups : groups.filter((g) => g.meta.id === dept)
  const bands = dept === "all" ? visible.slice(0, BAND_COUNT) : visible
  const rest = dept === "all" ? visible.slice(BAND_COUNT) : []
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
        <Standout agent={star} days={days} />
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
            <span className="rs-ddot" />
            {g.meta.name} <b>{g.agents.length}</b>
          </button>
        ))}
      </div>

      {bands.map((group) => (
        <DepartmentBand key={group.meta.id} group={group} starId={star?.id ?? null} />
      ))}

      {rest.length > 0 || showEmpty.length > 0 ? (
        <section className="rs-rest" aria-label="More of your team">
          {rest.length > 0 ? <h2>More of your team</h2> : null}
          <div className="rs-rest-grid">
            {rest.map(({ meta, agents: list }) => (
              <div key={meta.id} className={cn("gv-card rs-mini", `rs-d-${meta.id}`)}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="rs-dsq" />
                  <strong style={{ fontWeight: 600 }}>{meta.name}</strong>
                  <span className="cnt">{list.length}</span>
                </div>
                <ul>
                  {list.map((a) => (
                    <li key={a.id}>
                      <Link href={agentHref(a.id)}>
                        <AgentAvatar agent={a} size="sm" dot={false} />
                        <span style={{ flex: "1 1 auto", minWidth: 0 }}>{a.name}</span>
                        <span
                          className="gv-dot"
                          aria-label={a.state === "blocked" ? "Needs you" : a.state === "not_set_up" ? "Not set up" : "Ready"}
                          style={{
                            background:
                              a.state === "blocked"
                                ? "var(--gv-amber)"
                                : a.state === "not_set_up"
                                  ? "var(--gv-border-strong)"
                                  : "var(--gv-accent)",
                          }}
                        />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {showEmpty.map((meta) => (
              <div key={meta.id} className={cn("rs-emptydept", `rs-d-${meta.id}`)}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="rs-dsq" />
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
