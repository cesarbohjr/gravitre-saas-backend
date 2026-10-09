"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
import { useReducedMotion } from "framer-motion"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
import { departmentId } from "@/lib/goal-insights"
import { CONNECTOR_CATALOG } from "@/lib/connectors"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import {
  DEPARTMENT_BY_ID,
  blockedReason,
  buildWorkMap,
  litAgents,
  missingPieces,
  traceStory,
  wiredAgentIds,
  type MapOutput,
  type RosterAgent,
  type RosterGoal,
  type TraceKey,
} from "@/lib/agents-roster"
import { cn } from "@/lib/utils"
import { DEPARTMENT_ICONS } from "@/lib/department-icons"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import { agentHref, giveTaskHref } from "./agent-bits"
import { RosterNodeSheet, type MapNode } from "./roster-node-sheet"

// Geometry (px) — four lanes plus the approval gate, read left to right.
const W = 1200
const TOP = 92
const PITCH = 44
const APP = { x: 28, w: 164, h: 56 }
const AG = { x: 236, w: 326, h: 38 }
const OUT = { x: 610, w: 222, h: 34 }
const GATE_X = 884
const GOAL = { x: 938, w: 246, h: 140 }
const SUG_H = 112
/** Dormant agents listed under the connected ones before "see all" takes over. */
export const DORMANT_CAP = 6
const DROW = 34
/** Apps only dormant agents use, listed under the live ones. */
const IDLE_APP_CAP = 6
const IDLE_ROW = 40

const GOAL_CATEGORY: Record<string, string> = {
  sales: "sales",
  marketing: "marketing",
  customer_success: "support",
  finance: "finance",
  operations: "operations",
}

/** A goal phrase for an output nobody measures yet. Falls back to tracking it. */
const SUGGESTED_GOAL: Record<string, string> = {
  "Qualified leads": "Grow qualified leads",
  "Enriched contacts": "Keep every new lead fully enriched",
  "Deals moved": "Move more deals to the next stage",
  "Forecast and pipeline": "Keep the pipeline forecast accurate",
  "Executive briefs": "Brief leadership every week",
  "Visibility reports": "Grow search and AI visibility",
  "Campaigns sent": "Grow signups from campaigns",
  "Content drafts": "Publish content on a steady cadence",
  "Tickets routed": "Route every ticket within an hour",
  "Churn alerts": "Reduce churn",
  "Risk reports": "Close known risks faster",
  "Cash forecast": "Keep cash forecast current",
  "Code reviews": "Review every change before release",
}

function f(n: number) {
  return Math.round(n * 10) / 10
}
function curve(x1: number, y1: number, x2: number, y2: number) {
  const dx = (x2 - x1) * 0.5
  return `M${x1} ${f(y1)} C${f(x1 + dx)} ${f(y1)} ${f(x2 - dx)} ${f(y2)} ${x2} ${f(y2)}`
}
function mean(values: number[], fallback: number) {
  return values.length ? values.reduce((s, v) => s + v, 0) / values.length : fallback
}
function snap(v: number) {
  return TOP + 22 + Math.round((v - TOP - 22) / PITCH) * PITCH
}
/** Keep cards in a column from overlapping while staying near their ideal y. */
function place<T extends { y: number }>(items: T[], gap: number, min: number) {
  items.sort((a, b) => a.y - b.y)
  for (let i = 0; i < items.length; i++) {
    const floor = i === 0 ? min : items[i - 1].y + gap
    if (items[i].y < floor) items[i].y = floor
  }
}

type LinkState = "live" | "idle" | "blocked"
interface MapLink {
  d: string
  state: LinkState
  on: boolean
  step: number
}

function agentLinkState(a: RosterAgent): LinkState {
  if (a.state === "blocked") return "blocked"
  if (a.state === "working" || a.state === "active_today") return "live"
  return "idle"
}

function vendorKeys(apps: string[]): string[] {
  const keys: string[] = []
  for (const app of apps) {
    const hit = CONNECTOR_CATALOG.find(
      (c) => c.type.toLowerCase() === app.toLowerCase() || c.vendorKey === app.toLowerCase().replace(/[^a-z0-9]+/g, "_"),
    )
    if (hit) keys.push(hit.vendorKey)
  }
  return keys
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
}

export function RosterWorkMap({
  agents,
  goals,
  statsAvailable,
  initialTrace,
  onGoalsChanged,
  onSelectAgent,
  rawById,
  onChanged,
}: {
  agents: RosterAgent[]
  goals: RosterGoal[]
  statsAvailable: boolean
  initialTrace?: string | null
  onGoalsChanged: () => void
  onSelectAgent?: (agent: RosterAgent | null) => void
  /** Agents API rows by id, for the detail sheet. */
  rawById?: Map<string, Record<string, unknown>>
  onChanged?: () => Promise<unknown> | void
}) {
  const reduced = useReducedMotion()
  // Every agent, for insights and details; the lanes only draw fully wired agents.
  const fullModel = useMemo(() => buildWorkMap(agents, goals), [agents, goals])
  const wired = useMemo(() => wiredAgentIds(fullModel), [fullModel])
  const model = useMemo(() => buildWorkMap(agents.filter((a) => wired.has(a.id)), goals), [agents, goals, wired])
  const dormant = useMemo(() => fullModel.agents.filter((a) => !wired.has(a.id)), [fullModel, wired])
  const idleApps = useMemo(() => fullModel.apps.filter((p) => !model.apps.some((m) => m.name === p.name)), [fullModel, model])
  const [node, setNode] = useState<MapNode | null>(null)
  const defaultTrace = useMemo(() => {
    const fed = model.goals.find((g) => (model.goalAgents.get(g.id) ?? []).length > 0)
    return fed ? `goal:${fed.id}` : "all"
  }, [model])
  const [picked, setPicked] = useState<TraceKey | null>(initialTrace ?? null)
  const [hover, setHover] = useState<TraceKey | null>(null)
  const [live, setLive] = useState(true)
  const [sim, setSim] = useState(0)
  const [wizard, setWizard] = useState<null | { objective: string; department?: string; category?: string; metric?: string; systems?: string[] }>(null)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])
  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const sel: TraceKey = picked ?? defaultTrace
  const active: TraceKey = sim ? sel : hover ?? sel
  const [kind, ...rest] = active.split(":")
  const key = rest.join(":")
  const lit = useMemo(() => litAgents(model, active), [model, active])
  const byId = useMemo(() => new Map(fullModel.agents.map((a) => [a.id, a])), [fullModel])

  useEffect(() => {
    if (!onSelectAgent) return
    const [k, ...r] = sel.split(":")
    onSelectAgent(k === "agent" ? byId.get(r.join(":")) ?? null : null)
  }, [sel, byId, onSelectAgent])

  // ---- layout ----
  const layout = useMemo(() => {
    const agentY = new Map<string, number>()
    model.agents.forEach((a, i) => agentY.set(a.id, TOP + 22 + i * PITCH))
    const emptyH = model.agents.length ? 0 : 96
    const dormantY0 = TOP + 22 - AG.h / 2 + model.agents.length * PITCH + (model.agents.length ? 14 : 0) + emptyH
    const dormantShown = Math.min(dormant.length, DORMANT_CAP)
    const dormantH = dormant.length ? 72 + dormantShown * DROW + (dormant.length > DORMANT_CAP ? 34 : 8) : 0
    const bottomAgents = dormantY0 + dormantH + 24

    const apps = model.apps.map((p) => ({ ...p, y: snap(mean(p.agentIds.map((id) => agentY.get(id) ?? 0), TOP + 50)) }))
    // Many apps would overrun the agents lane at the roomy pitch, so tighten it.
    const appPitch = apps.length > 6 ? APP.h + 12 : PITCH * 2
    place(apps, appPitch, TOP + 50)
    const liveAppsBottom = apps.length ? apps[apps.length - 1].y + APP.h / 2 + 24 : TOP + 22
    const idleShown = Math.min(idleApps.length, IDLE_APP_CAP)
    const idleH = idleApps.length ? 58 + idleShown * IDLE_ROW + (idleApps.length > IDLE_APP_CAP ? 22 : 4) : 0
    const idleY0 = liveAppsBottom
    const appsBottom = idleY0 + idleH + 24

    const outs = model.outputs.map((o) => ({ ...o, y: snap(mean(o.agentIds.map((id) => agentY.get(id) ?? 0), TOP + 40)) }))
    place(outs, PITCH, TOP + 22)
    const outY = new Map(outs.map((o) => [o.name, o.y]))

    const goalCards = model.goals.map((g) => {
      const fed = model.outputs.filter((o) => o.goalIds.includes(g.id)).map((o) => outY.get(o.name) ?? 0)
      return { goal: g, y: Math.max(TOP + 78, mean(fed, TOP + 78)) }
    })
    place(goalCards, GOAL.h + 16, TOP + 78)
    const goalY = new Map(goalCards.map((c) => [c.goal.id, c.y]))
    const goalsBottom = goalCards.length ? goalCards[goalCards.length - 1].y + GOAL.h / 2 : TOP + 10

    const unmeasured = fullModel.unmeasuredOutputs
    const noneH = unmeasured.length ? 96 + Math.ceil(unmeasured.length / 2) * 23 : 0
    const noneIdeal = mean(unmeasured.map((o) => outY.get(o.name) ?? 0), goalsBottom) - noneH / 2
    const noneY0 = unmeasured.length ? Math.max(goalsBottom + 24, noneIdeal) : goalsBottom
    const sugY0 = (unmeasured.length ? noneY0 + noneH : goalsBottom) + 18
    const H = Math.max(bottomAgents, appsBottom, sugY0 + SUG_H + 24, TOP + 260)
    return { agentY, apps, outs, outY, goalCards, goalY, noneH, noneY0, sugY0, H, emptyH, dormantY0, dormantH, dormantShown, idleY0, idleH, idleShown }
  }, [model, fullModel, dormant.length, idleApps.length])

  // ---- suggested goal: the busiest output nobody measures ----
  const suggestion = useMemo(() => {
    let best: { out: MapOutput; work: number; lead: RosterAgent | null } | null = null
    for (const out of fullModel.unmeasuredOutputs) {
      const owners = out.agentIds.map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
      const work = owners.reduce((s, a) => s + (a.stats?.daily ?? []).reduce((x, y) => x + y, 0), 0)
      const lead = [...owners].sort((x, y) => y.tasksToday - x.tasksToday)[0] ?? null
      if (!best || work > best.work || (work === best.work && owners.length > best.out.agentIds.length)) best = { out, work, lead }
    }
    return best
  }, [fullModel, byId])

  // ---- links ----
  const links: MapLink[] = []
  const locks: { y: number; on: boolean; out: string }[] = []
  for (const a of model.agents) {
    const y = layout.agentY.get(a.id) ?? 0
    const on = lit.has(a.id)
    for (const app of a.apps) {
      const p = layout.apps.find((x) => x.name === app)
      if (p) links.push({ d: curve(APP.x + APP.w, p.y, AG.x, y), state: agentLinkState(a), on, step: 1 })
    }
    if (a.output) {
      const oy = layout.outY.get(a.output)
      if (oy != null) links.push({ d: curve(AG.x + AG.w, y, OUT.x, oy), state: agentLinkState(a), on, step: 2 })
    }
  }
  for (const o of layout.outs) {
    const owners = o.agentIds.map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
    const on = owners.some((a) => lit.has(a.id))
    const state: LinkState = owners.every((a) => a.state === "blocked")
      ? "blocked"
      : owners.some((a) => a.state === "working" || a.state === "active_today")
        ? "live"
        : "idle"
    const targets = o.goalIds.length ? o.goalIds.map((id) => layout.goalY.get(id) ?? TOP + 78) : [layout.noneY0 + 26]
    for (const ty of targets) {
      links.push({ d: curve(OUT.x + OUT.w, o.y, GOAL.x, ty), state, on, step: 3 })
      if (o.gated) locks.push({ y: f((o.y + ty) / 2), on, out: o.name })
    }
  }
  const simStepOn = (step: number) => sim > 0 && sim >= step

  // ---- trace options ----
  const options: { v: string; label: string }[] = [{ v: "all", label: "Everything" }]
  for (const g of model.goals) options.push({ v: `goal:${g.id}`, label: `Goal: ${g.objective}` })
  for (const a of model.agents) options.push({ v: `agent:${a.id}`, label: a.name })
  for (const p of model.apps) options.push({ v: `app:${p.name}`, label: `App: ${p.name}` })
  if (!options.some((o) => o.v === sel)) options.push({ v: sel, label: "Selection" })

  const counts = {
    wired: wired.size,
    working: fullModel.agents.filter((a) => a.state === "working" || a.state === "active_today").length,
    blocked: fullModel.agents.filter((a) => a.state === "blocked").length,
    dormant: dormant.length,
  }

  // ---- preview a run: walk the traced path one lane at a time (no data is written) ----
  const pathAgents = [...lit].map((id) => byId.get(id)).filter((a): a is RosterAgent => Boolean(a && a.output))
  const pathApps = [...new Set(pathAgents.flatMap((a) => a.apps))]
  const pathOuts = [...new Set(pathAgents.map((a) => a.output as string))]
  const pathGated = pathAgents.some((a) => a.gated)
  const pathGoals = model.goals.filter((g) => (model.goalAgents.get(g.id) ?? []).some((id) => lit.has(id)))
  const listNames = (xs: string[]) => (xs.length <= 1 ? xs[0] ?? "" : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`)
  const simStory = [
    "",
    pathApps.length ? `Step 1: the agents read from ${listNames(pathApps)}.` : "Step 1: these agents have no connected app, so they start from their instructions.",
    `Step 2: ${listNames(pathAgents.map((a) => a.name))} ${pathAgents.length === 1 ? "does" : "do"} the work.`,
    `Step 3: the work becomes ${listNames(pathOuts.map((o) => o.toLowerCase()))}.`,
    pathGated ? "Step 4: anything that writes to an app stops here until you approve it in the decision queue." : "Step 4: nothing on this path writes to an app, so no approval is needed.",
    pathGoals.length ? `Step 5: approved work counts toward ${listNames(pathGoals.map((g) => g.objective))}.` : "Step 5: this work is not tied to a goal yet, so nothing measures it.",
  ]
  const runSim = () => {
    timers.current.forEach(clearTimeout)
    timers.current = []
    if (sim) {
      setSim(0)
      return
    }
    setHover(null)
    setSim(1)
    for (let step = 2; step <= 5; step++) timers.current.push(setTimeout(() => setSim(step), (step - 1) * 1800))
  }
  const canPreview = pathAgents.length > 0

  const story = sim ? simStory[sim] : traceStory(model, active)

  // ---- story bar action ----
  let action: { href?: string; label: string; onClick?: () => void } | null = null
  if (!sim && kind === "goal" && key !== "none" && key) action = { href: `/goals/${encodeURIComponent(key)}`, label: "Open goal" }
  else if (!sim && kind === "agent" && byId.get(key)?.output) action = { href: giveTaskHref(key), label: "Give a task" }
  else if (!sim && kind === "agent" && byId.has(key)) action = { href: agentHref(key), label: "Set it up" }
  else if (!sim && kind === "app") action = { href: "/connectors", label: "Open connectors" }
  else if (sim === 4 && pathGated) action = { href: "/approvals", label: "Open decision queue" }

  // ---- bottom insights ----
  const goalSupply = (() => {
    const g = fullModel.goals.find((x) => (fullModel.goalAgents.get(x.id) ?? []).length > 0) ?? fullModel.goals[0]
    if (!g) return null
    const feeders = (fullModel.goalAgents.get(g.id) ?? []).map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
    const working = feeders.filter((a) => a.state === "working" || a.state === "active_today").length
    const blocked = feeders.filter((a) => a.state === "blocked").length
    return { g, feeders, working, blocked }
  })()
  const busiest = [...fullModel.agents].sort((x, y) => y.tasksToday - x.tasksToday)[0]
  const busiestOut = busiest?.output ? fullModel.outputs.find((o) => o.name === busiest.output) : undefined

  const openSuggested = () => {
    if (!suggestion) return
    const lead = suggestion.lead
    const owners = suggestion.out.agentIds.map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
    setWizard({
      objective: SUGGESTED_GOAL[suggestion.out.name] ?? `Track ${suggestion.out.name.toLowerCase()}`,
      department: lead ? DEPARTMENT_BY_ID.get(lead.department)?.name : undefined,
      category: lead ? GOAL_CATEGORY[lead.department] : undefined,
      metric: suggestion.out.name,
      systems: vendorKeys([...new Set(owners.flatMap((a) => a.apps))]),
    })
  }
  const openUnmeasured = () => {
    const outs = fullModel.unmeasuredOutputs
    const owners = outs.flatMap((o) => o.agentIds).map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
    setWizard({
      objective: outs.length === 1 ? SUGGESTED_GOAL[outs[0].name] ?? `Track ${outs[0].name.toLowerCase()}` : "",
      metric: outs.map((o) => o.name).join(", "),
      systems: vendorKeys([...new Set(owners.flatMap((a) => a.apps))]),
    })
  }

  const { H } = layout
  const showDots = live && !reduced
  const lanes = [
    { x: 16, w: 188, hx: 30, hw: 160, label: "Data from", count: plural(fullModel.apps.length, "app"), sub: "Connectors your agents read from and write to" },
    { x: 224, w: 350, hx: 240, hw: 318, label: "Agents", count: `${model.agents.length} of ${fullModel.agents.length} live`, sub: "Fully connected agents, then the dormant ones" },
    { x: 598, w: 246, hx: 614, hw: 214, label: "What they produce", count: String(model.outputs.length), sub: "The output each agent delivers" },
    { x: 856, w: 56, hx: 858, hw: 52, label: "Gate", count: "", sub: "Your OK", gate: true },
    { x: 926, w: 270, hx: 942, hw: 238, label: "Goals", count: String(model.goals.length), sub: "The result the work counts toward" },
  ]

  return (
    <>
      <section className="gv-card" style={{ overflow: "hidden" }} aria-label="Work map">
        <div className="wm-head">
          <div style={{ flex: "1 1 460px", minWidth: 0 }}>
            <div className="gv-eyebrow">Work map</div>
            <h1>From your apps, through your agents, to your goals</h1>
          </div>
          <div className="wm-counts" aria-label="Agent status">
            <span className="gv-pill brand">
              <span className="gv-ping" style={{ width: 7, height: 7, background: "var(--gv-accent)" }} />
              {counts.wired} fully connected
            </span>
            <span className="gv-pill neutral">{counts.working} working today</span>
            <span className="gv-pill amber">{counts.blocked} blocked</span>
            <span className="gv-pill rs-pill-off">{counts.dormant} dormant</span>
          </div>
          <div className="wm-controls">
            <label>
              Trace
              <select
                className="wm-pick"
                value={sel}
                onChange={(e) => {
                  setPicked(e.target.value)
                  setSim(0)
                }}
              >
                {options.map((o) => (
                  <option key={o.v} value={o.v}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            {canPreview ? (
              <button type="button" className="gv-btn primary sm" onClick={runSim}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                  <path d="M7 4.5v15l12-7.5z" />
                </svg>
                {sim ? "Reset preview" : "Preview a run"}
              </button>
            ) : null}
            <button type="button" className="gv-btn outline sm" aria-pressed={!live} onClick={() => setLive((v) => !v)}>
              {live ? "Pause motion" : "Play motion"}
            </button>
          </div>
        </div>
        <div className="wm-story" aria-live="polite">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#19C37D" strokeWidth="2" strokeLinejoin="round" style={{ flex: "0 0 auto" }} aria-hidden>
            <path d="M12 3c.6 3.9 2.1 5.4 6 6-3.9.6-5.4 2.1-6 6-.6-3.9-2.1-5.4-6-6 3.9-.6 5.4-2.1 6-6z" />
          </svg>
          <p key={story} className="gv-rise">
            {story}
          </p>
          {sim ? <span className="gv-pill">Preview · nothing is run or written</span> : null}
          {action ? (
            action.href ? (
              <Link className="gv-btn primary sm" href={action.href}>
                {action.label}
              </Link>
            ) : (
              <button type="button" className="gv-btn primary sm" onClick={action.onClick}>
                {action.label}
              </button>
            )
          ) : null}
        </div>
        <div className="wm-scroll">
          <div className={cn("wm-canvas", !live && "wm-paused")} style={{ height: H }} onMouseLeave={() => setHover(null)}>
            <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden>
              {lanes.map((ln) => (
                <rect key={ln.label} className={cn("wm-lane", ln.gate && "gate")} x={ln.x} y={12} width={ln.w} height={H - 20} rx={16} />
              ))}
              {links.map((l, i) => (
                <path
                  key={i}
                  d={l.d}
                  className={cn("wm-link", sim && simStepOn(l.step) && l.on ? "live" : l.state)}
                  opacity={l.on ? 1 : 0.14}
                />
              ))}
              {locks.map((k, i) => (
                <g key={i} className="wm-lock" opacity={k.on ? 1 : 0.14}>
                  <title>{`${k.out} waits for your approval`}</title>
                  <circle cx={GATE_X} cy={k.y} r={12} style={sim >= 4 && k.on ? { strokeWidth: 3 } : undefined} />
                  <path d={`M${GATE_X - 5} ${f(k.y - 1)}h10v7h-10zM${GATE_X - 3} ${f(k.y - 1)}v-2.5a3 3 0 0 1 6 0v2.5`} />
                </g>
              ))}
            </svg>

            {showDots
              ? links
                  .filter((l) => l.on && (l.state === "live" || (sim > 0 && simStepOn(l.step))))
                  .slice(0, 40)
                  .flatMap((l, i) => [0, 1].map((n) => (
                    <span
                      key={`${i}-${n}`}
                      className="wm-dot"
                      style={{ offsetPath: `path('${l.d}')`, animationDelay: `${-0.8 * n}s` } as CSSProperties}
                    />
                  )))
              : null}

            {lanes.map((ln) => (
              <div key={ln.label} className={cn("wm-lanehead", ln.gate && "gate")} style={{ left: ln.hx, width: ln.hw, textAlign: ln.gate ? "center" : "left" }}>
                <div style={{ display: "flex", justifyContent: ln.gate ? "center" : "space-between", gap: 6, alignItems: "baseline" }}>
                  <span className="wm-lt">{ln.label}</span>
                  {ln.count ? <span className="wm-lc">{ln.count}</span> : null}
                </div>
                <div className="wm-ls">{ln.sub}</div>
              </div>
            ))}

            {layout.apps.map((p, i) => {
              const on = p.agentIds.some((id) => lit.has(id))
              const isSel = kind === "app" && key === p.name
              return (
                <button
                  key={p.name}
                  type="button"
                  className={cn("wm-card wm-in", !on && "dim", isSel && "sel", sim === 1 && on && "lit-step")}
                  style={{ left: APP.x, top: p.y - APP.h / 2, width: APP.w, height: APP.h, animationDelay: `${i * 60}ms` }}
                  onClick={() => {
                    setPicked(`app:${p.name}`)
                    setNode({ kind: "app", key: p.name })
                  }}
                  onMouseEnter={() => !sim && setHover(`app:${p.name}`)}
                  aria-label={`${p.name}, ${plural(p.agentIds.length, "agent")} use it`}
                >
                  <span className="wm-logo" aria-hidden>
                    <ConnectorIcon vendor={p.name} size="md" showStatusIndicator={false} />
                  </span>
                  <span style={{ minWidth: 0 }}>
                    <span className="t1" style={{ fontSize: 13 }}>{p.name}</span>
                    <span className="t2" style={{ fontSize: 11 }}>{plural(p.agentIds.length, "agent")} use it</span>
                  </span>
                </button>
              )
            })}
            {idleApps.length ? (
              <div className="wm-group" style={{ left: APP.x - 6, top: layout.idleY0, width: APP.w + 12, height: layout.idleH }}>
                <b>Also connected</b>
                <span className="wm-group-sub">Only dormant agents use these</span>
                {idleApps.slice(0, IDLE_APP_CAP).map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    className="wm-grow"
                    onClick={() => setNode({ kind: "app", key: p.name })}
                    aria-label={`${p.name}, used by ${plural(p.agentIds.length, "dormant agent")}`}
                  >
                    <ConnectorIcon vendor={p.name} size="sm" showStatusIndicator={false} />
                    <span className="t1">{p.name}</span>
                  </button>
                ))}
                {idleApps.length > IDLE_APP_CAP ? (
                  <Link className="wm-group-more" href="/connectors">
                    +{idleApps.length - IDLE_APP_CAP} more in Connectors
                  </Link>
                ) : null}
              </div>
            ) : null}

            {model.agents.length === 0 ? (
              <div className="wm-noapp" style={{ left: AG.x, top: TOP + 8, width: AG.w, height: layout.emptyH - 16 }}>
                <b>No agent is fully connected yet</b>
                <span>An agent goes live here once it reads from a connector, produces an output and feeds a goal.</span>
              </div>
            ) : null}

            {dormant.length ? (
              <div className="wm-group wm-dormant" style={{ left: AG.x - 6, top: layout.dormantY0, width: AG.w + 12, height: layout.dormantH }}>
                <b>Dormant · {dormant.length}</b>
                <span className="wm-group-sub">Missing a connector, an output or a goal, so no work flows yet</span>
                {dormant.slice(0, DORMANT_CAP).map((a) => {
                  const missing = missingPieces(a, fullModel)
                  return (
                    <button
                      key={a.id}
                      type="button"
                      className="wm-grow"
                      onClick={() => setNode({ kind: "agent", key: a.id })}
                      aria-label={`${a.name}, dormant, needs ${missing.join(", ")}`}
                    >
                      <span className={cn("wm-agico rs-ava", `rs-d-${a.department}`)} aria-hidden>
                        <DeptGlyph department={a.department} />
                        <span className="d grey" />
                      </span>
                      <span style={{ flex: "1 1 auto", minWidth: 0 }}>
                        <span className="t1">{a.name}</span>
                      </span>
                      <span className="wm-need">Needs {missing[0]}</span>
                    </button>
                  )
                })}
                {dormant.length > DORMANT_CAP ? (
                  <Link className="wm-group-more" href="/agents?view=list">
                    See all {dormant.length} dormant agents in the list →
                  </Link>
                ) : null}
              </div>
            ) : null}

            {model.agents.map((a, i) => {
              const y = layout.agentY.get(a.id) ?? 0
              const on = lit.has(a.id)
              const isSel = kind === "agent" && key === a.id
              const tag =
                a.state === "working"
                  ? "WORKING"
                  : a.state === "active_today"
                    ? `${a.tasksToday} TODAY`
                    : a.state === "blocked"
                      ? "BLOCKED"
                      : a.state === "not_set_up"
                        ? "NOT SET UP"
                        : "READY"
              const dept = DEPARTMENT_BY_ID.get(a.department)?.name ?? a.departmentLabel
              return (
                <button
                  key={a.id}
                  type="button"
                  className={cn(
                    "wm-card wm-in",
                    !on && "dim",
                    isSel && "sel",
                    a.state === "blocked" && "blocked",
                    (a.state === "working" || a.state === "active_today") && "busy",
                    a.state === "not_set_up" && "ph",
                    sim === 2 && on && "lit-step",
                  )}
                  style={{ left: AG.x, top: y - AG.h / 2, width: AG.w, height: AG.h, padding: "0 10px", animationDelay: `${120 + i * 35}ms` }}
                  onClick={() => {
                    setPicked(`agent:${a.id}`)
                    setNode({ kind: "agent", key: a.id })
                  }}
                  onMouseEnter={() => !sim && setHover(`agent:${a.id}`)}
                  title={a.state === "blocked" ? blockedReason(a) ?? undefined : undefined}
                >
                  <span className={cn("wm-agico rs-ava", `rs-d-${a.department}`)} aria-hidden>
                    <DeptGlyph department={a.department} />
                    <span
                      className={cn(
                        "d",
                        a.state === "blocked" && "amber",
                        a.state === "not_set_up" && "grey",
                        (a.state === "working" || a.state === "active_today") && "blink",
                      )}
                    />
                  </span>
                  <span style={{ flex: "1 1 auto", minWidth: 0, lineHeight: 1.15 }}>
                    <span className="t1">{a.name}</span>
                    <span className="t2">{dept}</span>
                  </span>
                  <span className="wm-apps" aria-label={`Uses ${a.apps.join(", ")}`}>
                    {a.apps.slice(0, 3).map((app) => (
                      <ConnectorIcon key={app} vendor={app} name={app} size="xs" showStatusIndicator={false} />
                    ))}
                    {a.apps.length > 3 ? <span className="more">+{a.apps.length - 3}</span> : null}
                  </span>
                  <span className={cn("tag", (a.state === "working" || a.state === "active_today") && "ok", a.state === "blocked" && "amber")}>
                    {tag}
                  </span>
                </button>
              )
            })}

            {layout.outs.map((o, i) => {
              const owners = o.agentIds.map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
              const on = owners.some((a) => lit.has(a.id))
              const isSel = kind === "out" && key === o.name
              const blocked = owners.every((a) => a.state === "blocked")
              const busy = owners.some((a) => a.state === "working" || a.state === "active_today")
              return (
                <button
                  key={o.name}
                  type="button"
                  className={cn("wm-card wm-in", !on && "dim", isSel && "sel", sim === 3 && on && "lit-step")}
                  style={{ left: OUT.x, top: o.y - OUT.h / 2, width: OUT.w, height: OUT.h, animationDelay: `${240 + i * 40}ms` }}
                  onClick={() => {
                    setPicked(`out:${o.name}`)
                    setNode({ kind: "out", key: o.name })
                  }}
                  onMouseEnter={() => !sim && setHover(`out:${o.name}`)}
                >
                  <span className={cn("wm-bar4", blocked ? "amber" : busy ? "ok" : "")} aria-hidden />
                  <span className="t1" style={{ flex: "1 1 auto" }}>{o.name}</span>
                  {o.agentIds.length > 1 ? <span className="tag">{o.agentIds.length} agents</span> : null}
                </button>
              )
            })}

            {layout.goalCards.map(({ goal, y }) => {
              const feeders = (model.goalAgents.get(goal.id) ?? []).map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
              const on = feeders.some((a) => lit.has(a.id)) || (kind === "goal" && key === goal.id)
              const isSel = kind === "goal" && key === goal.id
              const blocked = feeders.filter((a) => a.state === "blocked").length
              const meta = [
                goal.status.charAt(0).toUpperCase() + goal.status.slice(1),
                goal.department || null,
                goal.priority ? `${goal.priority.charAt(0).toUpperCase()}${goal.priority.slice(1)} priority` : null,
              ]
                .filter(Boolean)
                .join(" · ")
              return (
                <button
                  key={goal.id}
                  type="button"
                  className={cn("wm-card wm-in wm-goal", !on && "dim", isSel && "sel", sim === 5 && on && "lit-step")}
                  style={{ left: GOAL.x, top: y - GOAL.h / 2, width: GOAL.w, height: GOAL.h }}
                  onClick={() => {
                    setPicked(`goal:${goal.id}`)
                    setNode({ kind: "goal", key: goal.id })
                  }}
                  onMouseEnter={() => !sim && setHover(`goal:${goal.id}`)}
                >
                  <span className="top" />
                  <span className="in">
                    <span className="ttl">{goal.objective || "Untitled goal"}</span>
                    <span className="meta">{meta}</span>
                    <span className="meta">Progress not reported yet</span>
                    <span className={cn("note", blocked > 0 && "amber")}>
                      {feeders.length === 0
                        ? "No agent feeds it yet"
                        : `${plural(feeders.length, "agent")} feed${feeders.length === 1 ? "s" : ""} it${blocked ? ` · ${blocked} blocked` : ""}`}
                    </span>
                  </span>
                </button>
              )
            })}
            {model.goals.length === 0 ? (
              <div className="wm-noapp" style={{ left: GOAL.x, top: TOP + 10, width: GOAL.w, height: 74 }}>
                <b>No goals yet</b>
                <span>Goals show which work moves the business.</span>
                <Link href="/goals">Go to goals</Link>
              </div>
            ) : null}

            {fullModel.unmeasuredOutputs.length ? (
              <div className="wm-card wm-none" style={{ left: GOAL.x, top: layout.noneY0, width: GOAL.w, height: layout.noneH, cursor: "default" }}>
                <span>
                  <span className="t1" style={{ fontSize: 14, fontWeight: 700 }}>Not tied to a goal</span>
                  <span className="t2" style={{ fontSize: 11 }}>
                    {plural(fullModel.unmeasuredOutputs.length, "output")} nobody is measuring
                  </span>
                </span>
                <span className="chips">
                  {fullModel.unmeasuredOutputs.map((o) => (
                    <button key={o.name} type="button" onClick={() => setNode({ kind: "out", key: o.name })}>
                      {o.name}
                    </button>
                  ))}
                </span>
                <button type="button" className="cta" onClick={openUnmeasured} style={{ border: 0, background: "transparent", padding: 0, cursor: "pointer" }}>
                  + Create a goal for these
                </button>
              </div>
            ) : null}

            {suggestion ? (
              <button
                type="button"
                className="wm-card wm-sug"
                style={{ left: GOAL.x, top: layout.sugY0, width: GOAL.w, height: SUG_H }}
                onClick={openSuggested}
              >
                <span className="eb">SUGGESTED GOAL</span>
                <span className="s1">{SUGGESTED_GOAL[suggestion.out.name] ?? `Track ${suggestion.out.name.toLowerCase()}`}</span>
                <span className="s2">
                  {suggestion.work > 0 && suggestion.lead
                    ? `Measures ${suggestion.lead.name}'s busiest work`
                    : `Gives ${plural(suggestion.out.agentIds.length, "agent")} a result to aim for`}
                </span>
                <span className="s3">Create this goal →</span>
              </button>
            ) : null}
          </div>
        </div>
      </section>

      <section aria-label="What the map shows" className="rs-insights wm-bottom">
        {goalSupply ? (
          <button
            type="button"
            className={cn("rs-ins", sel === `goal:${goalSupply.g.id}` && "on")}
            onClick={() => setPicked(`goal:${goalSupply.g.id}`)}
          >
            <span className={cn("ic", goalSupply.working ? "mint" : "amber")}>{goalSupply.working}</span>
            <span>
              <span className="title">
                {goalSupply.feeders.length === 0
                  ? `${goalSupply.g.objective} has no agents yet`
                  : goalSupply.working
                    ? `${goalSupply.g.objective} is being fed`
                    : `${fullModel.goals.length === 1 ? "Your one goal" : goalSupply.g.objective} has no working supply`}
              </span>
              <span className="body" style={{ display: "block" }}>
                {goalSupply.feeders.length === 0
                  ? "Give it a plan or move an agent into its department."
                  : goalSupply.working
                    ? `${goalSupply.working} of its ${plural(goalSupply.feeders.length, "agent")} ran today.`
                    : `${goalSupply.feeders.length === 1 ? "The agent" : `All ${goalSupply.feeders.length} agents`} behind it ${goalSupply.feeders.length === 1 ? "is" : "are"} idle today${goalSupply.blocked ? `, and ${goalSupply.blocked} ${goalSupply.blocked === 1 ? "is" : "are"} blocked` : ""}.`}
              </span>
            </span>
          </button>
        ) : (
          <button type="button" className="rs-ins" onClick={() => setWizard({ objective: "" })}>
            <span className="ic">0</span>
            <span>
              <span className="title">No goals yet</span>
              <span className="body" style={{ display: "block" }}>Create a goal to see which agents move it.</span>
            </span>
          </button>
        )}
        {busiest && busiest.tasksToday > 0 ? (
          <button type="button" className={cn("rs-ins", sel === `agent:${busiest.id}` && "on")} onClick={() => setPicked(`agent:${busiest.id}`)}>
            <span className="ic mint">{busiest.tasksToday}</span>
            <span>
              <span className="title">{busiest.name} carries today</span>
              <span className="body" style={{ display: "block" }}>
                {fullModel.agents.filter((a) => a.tasksToday > 0).length === 1 ? "The only agent that ran today" : "The busiest agent today"}
                {busiestOut ? (busiestOut.goalIds.length ? `, and its ${busiestOut.name.toLowerCase()} count toward a goal.` : `, and its ${busiestOut.name.toLowerCase()} are not tied to a goal.`) : "."}
              </span>
            </span>
          </button>
        ) : (
          <button type="button" className={cn("rs-ins", sel === "all" && "on")} onClick={() => setPicked("all")}>
            <span className="ic">0</span>
            <span>
              <span className="title">{statsAvailable ? "Nobody has run today" : "Today's runs are not reported"}</span>
              <span className="body" style={{ display: "block" }}>
                {statsAvailable ? "Give an agent a task and its path lights up here." : "Activity will appear once runs are reported."}
              </span>
            </span>
          </button>
        )}
        <button type="button" className="rs-ins" onClick={fullModel.unmeasuredOutputs.length ? openUnmeasured : () => setPicked("all")}>
          <span className="ic">{fullModel.unmeasuredOutputs.length}</span>
          <span>
            <span className="title">Work nobody is measuring</span>
            <span className="body" style={{ display: "block" }}>
              {fullModel.unmeasuredOutputs.length
                ? "Outputs with no goal behind them. Create goals to see their impact."
                : "Every output feeds a goal."}
            </span>
          </span>
        </button>
      </section>

      <RosterNodeSheet
        node={node}
        onOpenChange={(open) => {
          if (!open) setNode(null)
        }}
        onOpenNode={setNode}
        model={fullModel}
        wired={wired}
        rawById={rawById}
        onChanged={onChanged}
      />

      <GoalWorkflowWizard
        open={wizard !== null}
        onOpenChange={(open) => {
          if (!open) setWizard(null)
        }}
        template={
          wizard
            ? {
                objective: wizard.objective,
                department: departmentId(wizard.department ?? wizard.category),
                metric: wizard.metric,
                systems: wizard.systems,
              }
            : null
        }
        onGoalSaved={onGoalsChanged}
      />
    </>
  )
}

function DeptGlyph({ department }: { department: AgentDepartmentId }) {
  const Icon = DEPARTMENT_ICONS[department] ?? DEPARTMENT_ICONS.general
  return <Icon size={14} strokeWidth={2} aria-hidden />
}
