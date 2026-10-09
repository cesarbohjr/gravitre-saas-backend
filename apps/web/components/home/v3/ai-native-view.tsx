"use client"

import { useMemo, useState, type FormEvent } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { workforceState } from "@/components/home/operating-flow"
import { APP_ROUTES } from "@/lib/app-routes"
import { DepartmentIcon } from "@/components/agents/department-icon"
import { relativeTime } from "@/lib/agent-job-result"
import { approvalsApi } from "@/lib/api"
import { approveAssignment, type DemoAssignment } from "@/lib/demo-assignments"
import type { Agent } from "@/types/api"

const GREEN = "#19C37D"
const AMBER = "#E2A33A"
const MINT = "#CDEBDC"
const GREY = "#8A8B85"
const RED = "#C2412D"
const BLUE = "#2B59E0"

export type PendingApproval = {
  id: string
  title: string
  description?: string | null
  action?: string | null
  requestedByName?: string | null
  requestedAt?: string | null
}

export type AiNativeData = {
  agents: Agent[]
  /** The agents list arrived; false while loading or after a failed fetch. */
  agentsLoaded: boolean
  agentsFailed: boolean
  /** Both the approval queue and assignments arrived (or failed), so an empty list really is empty. */
  decisionsLoaded: boolean
  approvals: PendingApproval[]
  assignments: DemoAssignment[] | undefined
  runsThisWeek: number | null
  activeConnectors: number | null
  approvalPolicies: number | null
  hasCustomReports: boolean
}

type LiveState = "exec" | "wait" | "idle" | "fault" | "paused"

type Decision = {
  id: string
  kind: "approval" | "assignment"
  agent: string
  step: string
  title: string
  why: string
  reviewHref: string
}

function shortName(name: string) {
  return name.replace(/\s+agent$/i, "").trim() || name
}

function joinNames(names: string[]) {
  if (names.length <= 1) return names[0] ?? ""
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

function firstName(full: string | null | undefined) {
  const n = String(full ?? "").trim().split(/\s+/)[0]
  return n ? n.charAt(0).toUpperCase() + n.slice(1) : ""
}

function greeting(now = new Date()) {
  const h = now.getHours()
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
}

function stepLabel(a: DemoAssignment) {
  const steps = a.steps ?? []
  if (steps.length === 0) return "Waiting for you"
  const current = steps.findIndex((s) => s.status !== "done")
  const at = current < 0 ? steps.length : current + 1
  return `Step ${at} of ${steps.length}`
}

/** Decisions waiting on the viewer: agent assignments paused for approval, then approval queue items. */
export function buildDecisions(data: AiNativeData): Decision[] {
  const out: Decision[] = []
  for (const a of (data.assignments ?? []).filter((x) => x.status === "needs_approval")) {
    out.push({
      id: `assignment:${a.id}`,
      kind: "assignment",
      agent: a.agent.name,
      step: stepLabel(a),
      title: a.title,
      why: a.approvalPrompt || "Paused before an action that needs your OK. The draft is ready to review.",
      reviewHref: `/assignments/${a.id}?approval=1`,
    })
  }
  for (const item of data.approvals) {
    out.push({
      id: `approval:${item.id}`,
      kind: "approval",
      agent: item.requestedByName && item.requestedByName !== "System" ? item.requestedByName : "Workflow",
      // Connector action keys (hubspot.contacts.create) are not shown to people.
      step: item.action && /\s/.test(item.action) && !/[._]/.test(item.action) ? item.action : "Needs approval",
      title: item.title,
      why: item.description || "Paused because this step needs your approval before it runs.",
      reviewHref: `${APP_ROUTES.approvals}?id=${encodeURIComponent(item.id)}`,
    })
  }
  return out
}

function liveStates(data: AiNativeData) {
  const waitingNames = new Set(
    (data.assignments ?? []).filter((a) => a.status === "needs_approval").map((a) => a.agent.name.toLowerCase()),
  )
  const runningNames = new Set(
    (data.assignments ?? []).filter((a) => a.status === "running").map((a) => a.agent.name.toLowerCase()),
  )
  return data.agents.map((agent) => {
    const base = workforceState(agent.status)
    const name = agent.name.toLowerCase()
    const state: LiveState = waitingNames.has(name)
      ? "wait"
      : base === "executing" || runningNames.has(name)
        ? "exec"
        : base === "attention"
          ? "fault"
          : base === "paused"
            ? "paused"
            : "idle"
    return { agent, state }
  })
}

const ORDER: LiveState[] = ["wait", "exec", "fault", "idle", "paused"]

function nodeStyle(state: LiveState) {
  if (state === "exec") return { chip: "Executing", fg: "#0A6B47", dot: GREEN, line: GREEN, flow: 1, lift: true }
  if (state === "wait") return { chip: "Needs approval", fg: "#8A5A06", dot: AMBER, line: AMBER, flow: 1, lift: true }
  if (state === "fault") return { chip: "Needs attention", fg: RED, dot: RED, line: RED, flow: 1, lift: false }
  if (state === "paused") return { chip: "Paused", fg: "#55564F", dot: GREY, line: "#33342F", flow: 0, lift: false }
  return { chip: "Available", fg: "#55564F", dot: GREY, line: "#33342F", flow: 0, lift: false }
}

const NODE_SLOTS = [
  { x: 360, y: 64, trace: "M314 186 C 340 150 346 100 360 84" },
  { x: 380, y: 114, trace: "M316 190 C 352 160 366 140 380 134" },
  { x: 360, y: 164, trace: "M316 196 C 346 192 350 186 360 184" },
]

/** Page-header scene from the design: the viewer relaxing while their department agents work. */
function HeroScene({ nodes }: { nodes: Array<{ id: string; label: string; state: LiveState }> }) {
  const label = nodes.length
    ? `A person relaxing at their desk while ${joinNames(nodes.map((n) => n.label))} agents work`
    : "A person relaxing at their desk"
  return (
    <svg viewBox="0 0 520 340" width="100%" style={{ display: "block" }} role="img" aria-label={label}>
      <image href="/illustrations/home-hero.svg?v=2" x={0} y={0} width={520} height={340} />
      {nodes.map((n, i) => {
        const slot = NODE_SLOTS[i]
        const s = nodeStyle(n.state)
        return (
          <path key={`trace-${n.id}`} d={slot.trace} fill="none" stroke={s.line} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="gv-trace" pathLength={100} opacity={s.flow} />
        )
      })}
      {nodes.map((n, i) => {
        const slot = NODE_SLOTS[i]
        const s = nodeStyle(n.state)
        const text = n.label.length > 18 ? `${n.label.slice(0, 17)}…` : n.label
        return (
          <g key={n.id} className="gv-node" style={{ transform: s.lift ? "translateY(-6px)" : undefined }}>
            <title>{`${n.label}: ${s.chip}`}</title>
            <rect x={slot.x} y={slot.y} width={136} height={40} rx={9} fill="#FBF8F2" stroke="#D9D1C2" strokeWidth={1.5} />
            <circle cx={slot.x + 15} cy={slot.y + 20} r={4.5} fill={s.dot} />
            <text x={slot.x + 27} y={slot.y + 17} fontFamily="var(--font-sans), sans-serif" fontSize={11} fontWeight={600} fill="#141513">
              {text}
            </text>
            <text x={slot.x + 27} y={slot.y + 30} fontFamily="var(--font-mono), monospace" fontSize={9.5} fill={s.fg}>
              {s.chip}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

const HEART_IDLE = "M2 16 L18 16 L24 14 L30 16 L82 16"
const HEART_ACTIVE = "M2 16 L16 16 L22 6 L28 24 L34 10 L40 18 L46 16 L56 16 L62 8 L68 22 L74 16 L82 16"

type ChangeItem = { id: string; text: string; meta: string; color: string; href: string; at: number }

/** Agent work since yesterday from assignments; agents with nothing new show their last known action. */
export function buildChanges(data: AiNativeData, approvedCount: number, now = Date.now()): ChangeItem[] {
  const since = now - 24 * 60 * 60 * 1000
  const items: ChangeItem[] = []
  for (const a of data.assignments ?? []) {
    const ts = Date.parse(a.completedAt || a.createdAtIso || "")
    if (!Number.isFinite(ts) || ts < since) continue
    if (a.status === "completed") {
      items.push({ id: a.id, text: a.resultSummary || `Finished “${a.title}”`, meta: `${a.agent.name} · ${relativeTime(new Date(ts).toISOString())}`, color: GREEN, href: `/assignments/${a.id}`, at: ts })
    } else if (a.status === "failed") {
      items.push({ id: a.id, text: `Could not finish “${a.title}”`, meta: `${a.agent.name} · ${relativeTime(new Date(ts).toISOString())}`, color: RED, href: `/assignments/${a.id}`, at: ts })
    } else if (a.status === "running") {
      items.push({ id: a.id, text: `Started “${a.title}”`, meta: `${a.agent.name} · ${relativeTime(new Date(ts).toISOString())}`, color: BLUE, href: `/assignments/${a.id}`, at: ts })
    }
  }
  items.sort((x, y) => y.at - x.at)
  const seen = new Set(items.map((i) => i.meta.split(" · ")[0].toLowerCase()))
  for (const agent of data.agents) {
    if (items.length >= 5) break
    if (seen.has(agent.name.toLowerCase())) continue
    const quiet = !agent.lastAction || /no recent activity/i.test(agent.lastAction)
    items.push({
      id: `agent-${agent.id}`,
      text: quiet ? "No recent activity" : agent.lastAction,
      meta: `${agent.name} · ${agent.lastActionTime ? relativeTime(agent.lastActionTime) : "recently"}`,
      color: quiet ? GREY : BLUE,
      href: `${APP_ROUTES.agents}/${agent.id}`,
      at: 0,
    })
  }
  if (approvedCount) {
    items.unshift({ id: "approved-now", text: `You approved ${approvedCount} ${approvedCount === 1 ? "action" : "actions"}`, meta: "Just now", color: GREEN, href: APP_ROUTES.approvals, at: now })
  }
  return items.slice(0, 5)
}

type StartCard = { id: string; title: string; body: string; href: string; tint: string; stroke: string; icon: "play" | "plug" | "shield" | "grid" | "bot" | "assign" }

export function buildStartNext(data: AiNativeData): StartCard[] {
  const cards: StartCard[] = []
  const salesAgent = data.agents.find((a) => /sales/i.test(`${a.department} ${a.name}`))
  if (data.agentsLoaded && data.agents.length === 0) {
    cards.push({ id: "hire", title: "Hire your first agent", body: "Pick a department and Gravitre sets up an agent with the right tools.", href: `${APP_ROUTES.agents}/new`, tint: "var(--gv-mint)", stroke: "#0B8A5C", icon: "bot" })
  }
  if (data.runsThisWeek === 0) {
    cards.push({ id: "run", title: "Run your first workflow", body: "No runs this week. A test run fills every chart on Reports.", href: APP_ROUTES.workflows, tint: "var(--gv-mint)", stroke: "#0B8A5C", icon: "play" })
  }
  if (data.activeConnectors === 0) {
    cards.push({ id: "connect", title: "Connect a data source", body: salesAgent ? `Give the ${salesAgent.name} your CRM so it can qualify leads.` : "Connect your CRM or inbox so agents can work with real records.", href: APP_ROUTES.connectors, tint: "var(--gv-blue-bg)", stroke: "#2B59E0", icon: "plug" })
  }
  if (data.approvalPolicies === 0) {
    cards.push({ id: "policy", title: "Set an approval policy", body: "Choose which actions always pause for your decision.", href: "/settings/approvals", tint: "var(--gv-amber-bg)", stroke: "#8A5A06", icon: "shield" })
  }
  if (!data.hasCustomReports) {
    cards.push({ id: "master", title: "Build your master view", body: "Drag KPIs into a Reports layout that fits your role.", href: "#reports", tint: "var(--gv-subtle)", stroke: "var(--gv-text)", icon: "grid" })
  }
  const fill: StartCard[] = [
    { id: "assign", title: "Assign work to an agent", body: "Describe the outcome you want and pick who does it.", href: "/assignments/new", tint: "var(--gv-mint)", stroke: "#0B8A5C", icon: "assign" },
    { id: "connectors-more", title: "Connect another system", body: "More connected tools means agents can finish more on their own.", href: APP_ROUTES.connectors, tint: "var(--gv-blue-bg)", stroke: "#2B59E0", icon: "plug" },
    { id: "policy-review", title: "Review approval rules", body: "Check which actions pause for your decision.", href: "/settings/approvals", tint: "var(--gv-amber-bg)", stroke: "#8A5A06", icon: "shield" },
    { id: "reports", title: "Open your reports", body: "See runs, success rate and time saved by agent.", href: "#reports", tint: "var(--gv-subtle)", stroke: "var(--gv-text)", icon: "grid" },
  ]
  for (const f of fill) {
    if (cards.length >= 4) break
    if (!cards.some((c) => c.icon === f.icon)) cards.push(f)
  }
  return cards.slice(0, 4)
}

function StartIcon({ icon, stroke }: { icon: StartCard["icon"]; stroke: string }) {
  const common = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke, strokeWidth: 2, strokeLinecap: "round" as const, "aria-hidden": true }
  if (icon === "play") return <svg {...common}><path d="M7 4.5v15l12-7.5z" /></svg>
  if (icon === "plug") return <svg {...common}><path d="M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4" /></svg>
  if (icon === "shield") return <svg {...common}><path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z" /></svg>
  if (icon === "bot") return <svg {...common}><rect x="4" y="7" width="16" height="13" rx="3" /><path d="M12 7V4M9 13h.01M15 13h.01" /></svg>
  if (icon === "assign") return <svg {...common}><path d="M4 6h10M4 12h8M4 18h6M15 16l2 2 4-4" /></svg>
  return (
    <svg {...common} strokeLinecap={undefined}>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="17" height="7" rx="1.5" />
    </svg>
  )
}

export function AiNativeView({
  data,
  userName,
  onOpenReports,
  onDecided,
}: {
  data: AiNativeData
  userName: string | null
  onOpenReports: () => void
  onDecided: () => void
}) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()
  const [query, setQuery] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [done, setDone] = useState<string[]>([])

  const allDecisions = useMemo(() => buildDecisions(data), [data])
  const decisions = allDecisions.filter((d) => !done.includes(d.id))
  const live = useMemo(() => liveStates(data), [data])
  const sorted = useMemo(() => [...live].sort((a, b) => ORDER.indexOf(a.state) - ORDER.indexOf(b.state)), [live])
  const executing = live.filter((l) => l.state === "exec").length
  const waiting = live.filter((l) => l.state === "wait").length
  const faults = live.filter((l) => l.state === "fault").length
  const enabled = live.filter((l) => l.state !== "paused").length
  const available = live.filter((l) => l.state === "idle").length
  const changes = useMemo(() => buildChanges(data, done.length), [data, done.length])
  const start = useMemo(() => buildStartNext(data), [data])

  const decidingAgents = Array.from(new Set(decisions.map((d) => (d.kind === "assignment" ? shortName(d.agent) : "")).filter(Boolean)))
  const workflowDecisions = decisions.filter((d) => d.kind === "approval").length
  const pausedWho = [...decidingAgents, ...(workflowDecisions ? [`${workflowDecisions} workflow${workflowDecisions === 1 ? "" : "s"}`] : [])]
  const subline = decisions.length
    ? `${joinNames(pausedWho)} ${pausedWho.length === 1 && !/workflows$/.test(pausedWho[0]) ? "is" : "are"} paused for your approval. ${available} ${available === 1 ? "agent" : "agents"} available.`
    : !data.agentsLoaded
      ? "Nothing needs your decision right now."
      : data.agents.length
        ? `Nothing needs your decision. ${executing} executing, ${available} available.`
        : "Nothing needs your decision. Hire an agent to start delegating work."

  const segments = sorted.map((l) => ({ id: l.agent.id, name: l.agent.name, state: l.state }))
  const legend = [
    executing ? { color: GREEN, n: executing, label: "executing" } : null,
    waiting ? { color: AMBER, n: waiting, label: "waiting" } : null,
    faults ? { color: RED, n: faults, label: "need attention" } : null,
    { color: MINT, n: available, label: "available" },
  ].filter(Boolean) as Array<{ color: string; n: number; label: string }>
  const heroPicks = sorted.slice(0, 3)
  const depts = heroPicks.map((l) => String(l.agent.department ?? ""))
  // Department name when it is distinct among the three nodes, the agent's own name otherwise.
  const heroNodes = heroPicks.map((l, i) => ({
    id: l.agent.id,
    label: depts[i] && depts.filter((d) => d === depts[i]).length === 1 ? depts[i] : shortName(l.agent.name),
    state: l.state,
  }))

  const firstDecision = decisions[0]
  const suggestions = [
    "What changed since yesterday?",
    data.runsThisWeek === 0 ? "Why were there no runs this week?" : "What ran this week and did anything fail?",
    firstDecision ? `Summarize “${firstDecision.title}” before I approve it` : "What should I delegate next?",
    "Build an agent from a workflow",
  ]

  const ask = (text: string) => {
    const prompt = text.trim()
    if (!prompt) return
    summonWorkspace({ presentation: "compact", composerText: prompt, submit: true, selected: pageContext.selected })
    setQuery("")
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    ask(query)
  }

  const approve = async (d: Decision) => {
    setBusy(d.id)
    try {
      const raw = d.id.split(":").slice(1).join(":")
      if (d.kind === "assignment") await approveAssignment(raw)
      else await approvalsApi.approve(raw)
      setDone((prev) => [...prev, d.id])
      toast.success("Approved. The agent is continuing.")
      onDecided()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not approve. Try again from Approvals.")
    } finally {
      setBusy(null)
    }
  }

  const name = firstName(userName)

  return (
    <div data-dashboard-view="ai">
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 440px), 1fr))", gap: 40, alignItems: "center", padding: "48px 0 32px" }}>
        <div className="gv-rise">
          <div className="gv-mono" style={{ fontSize: 11, color: "var(--gv-muted)", marginBottom: 18 }}>
            {greeting()}
            {name ? `, ${name}` : ""}
          </div>
          {!data.decisionsLoaded ? (
            <div style={{ display: "grid", gap: 12 }} aria-label="Loading decisions">
              <div className="gv-skel" style={{ width: "70%", height: 40 }} />
              <div className="gv-skel" style={{ width: "85%" }} />
            </div>
          ) : decisions.length ? (
            <h2 style={{ margin: 0, fontSize: 44, lineHeight: 1.1, fontWeight: 600, letterSpacing: "-0.025em" }}>
              <span style={{ color: "var(--gv-amber-text)" }}>{decisions.length === 1 ? "1 decision" : `${decisions.length} decisions`}</span> need{decisions.length === 1 ? "s" : ""} you.
            </h2>
          ) : (
            <h2 style={{ margin: 0, fontSize: 44, lineHeight: 1.1, fontWeight: 600, letterSpacing: "-0.025em" }}>
              <span style={{ color: "var(--gv-brand)" }}>All clear.</span>
            </h2>
          )}
          {data.decisionsLoaded ? (
            <p style={{ margin: "14px 0 0", fontSize: 18, lineHeight: 1.5, color: "var(--gv-muted)", maxWidth: 520 }}>{subline}</p>
          ) : null}

          <div style={{ marginTop: 32 }}>
            <div style={{ display: "flex", gap: 6, height: 12 }} aria-hidden>
              {segments.length === 0 ? <div style={{ flex: 1, borderRadius: 4, background: "var(--gv-subtle)" }} /> : null}
              {segments.map((s) => (
                <div
                  key={s.id}
                  title={`${s.name} · ${nodeStyle(s.state).chip}`}
                  className={s.state === "exec" ? "gv-seg-exec" : undefined}
                  style={{ flex: 1, borderRadius: 4, backgroundColor: s.state === "wait" ? AMBER : s.state === "fault" ? RED : s.state === "exec" ? GREEN : s.state === "paused" ? "var(--gv-subtle)" : MINT }}
                />
              ))}
            </div>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginTop: 12, fontSize: 14, color: "var(--gv-muted)" }}>
              {legend.map((l) => (
                <span key={l.label} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: l.color }} />
                  <strong style={{ color: "var(--gv-text)", fontWeight: 600 }}>{l.n}</strong> {l.label}
                </span>
              ))}
              <Link href={APP_ROUTES.agents} style={{ textDecoration: "none", fontWeight: 500 }}>
                {enabled} of {live.length} enabled →
              </Link>
            </div>
          </div>
        </div>

        <div className="gv-rise" style={{ animationDelay: "120ms", position: "relative" }}>
          <div className="gv-card" style={{ padding: 0, borderRadius: 14, overflow: "hidden", background: "#F3EEE4", borderColor: "var(--gv-paper-border)" }}>
            <HeroScene nodes={heroNodes} />
          </div>
        </div>
      </section>

      <section className="gv-rise" style={{ animationDelay: "200ms" }}>
        <form onSubmit={submit} className="gv-card gv-composer" style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 10px 10px 22px", borderRadius: 14 }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth={1.8} strokeLinecap="round" aria-hidden>
            <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
          </svg>
          <label htmlFor="gvAsk" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
            Ask Gravitre
          </label>
          <input id="gvAsk" className="gv-input" placeholder="Ask Gravitre anything about your agents, runs or pipeline" value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off" />
          <button type="submit" className="gv-btn dark" style={{ minHeight: 48, padding: "0 20px" }}>
            Ask <span className="gv-mono" style={{ fontSize: 12, opacity: 0.6 }}>↵</span>
          </button>
        </form>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 14 }}>
          {suggestions.map((s) => (
            <button key={s} className="gv-chip" type="button" onClick={() => ask(s)}>
              <span style={{ color: "var(--gv-brand)" }}>↳</span>
              {s}
            </button>
          ))}
        </div>
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 380px), 1fr))", gap: 24, marginTop: 40, alignItems: "start" }}>
        <div className="gv-card gv-rise" style={{ padding: 24, animationDelay: "260ms" }} data-dashboard-decisions="">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Needs your decision</h3>
            <span className="gv-mono" style={{ fontSize: 13, color: "var(--gv-muted)" }}>{data.decisionsLoaded ? `${decisions.length} open` : ""}</span>
          </div>
          {!data.decisionsLoaded ? (
            <div style={{ display: "grid", gap: 14, padding: "14px 0" }}>
              <div className="gv-skel" style={{ width: "90%", height: 96 }} />
              <div className="gv-skel" style={{ width: "90%", height: 96 }} />
            </div>
          ) : decisions.length ? (
            <div style={{ display: "grid", gap: 14 }}>
              {decisions.slice(0, 3).map((d) => (
                <article key={d.id} className="gv-rise" style={{ border: "1px solid var(--gv-amber-border)", background: "var(--gv-amber-bg)", borderRadius: 14, padding: 18 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--gv-amber-text)", fontWeight: 600, marginBottom: 8 }}>
                    <span className="gv-ping" style={{ background: AMBER, width: 8, height: 8 }} />
                    {d.agent} · {d.step}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.35 }}>{d.title}</div>
                  <div style={{ fontSize: 14, color: "var(--gv-muted)", marginTop: 6, lineHeight: 1.5 }}>{d.why}</div>
                  <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
                    <button type="button" className="gv-btn primary" disabled={busy === d.id} onClick={() => void approve(d)}>
                      {busy === d.id ? "Approving…" : "Approve"}
                    </button>
                    <Link className="gv-btn ghost" href={d.reviewHref}>
                      Review first
                    </Link>
                  </div>
                </article>
              ))}
              {decisions.length > 3 ? (
                <Link href={APP_ROUTES.approvals} style={{ fontSize: 14, fontWeight: 500, textDecoration: "none" }}>
                  See all {decisions.length} decisions →
                </Link>
              ) : null}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "28px 12px" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/illustrations/home-all-clear.svg" alt="Person stretching, all clear" width={260} height={195} style={{ display: "block", width: "100%", maxWidth: 260, height: "auto", borderRadius: 12 }} />
              <div style={{ fontWeight: 600, marginTop: 14 }}>Inbox zero for decisions</div>
              <div style={{ fontSize: 14, color: "var(--gv-muted)", marginTop: 4, maxWidth: 280 }}>
                Agents will pause here before anything irreversible, like sending email or changing a deal.
              </div>
            </div>
          )}
        </div>

        <div className="gv-card gv-rise" style={{ padding: 24, animationDelay: "320ms" }} data-dashboard-agents="">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Agents, live</h3>
            <button type="button" onClick={onOpenReports} style={{ font: "inherit", fontSize: 14, fontWeight: 500, color: "var(--gv-brand)", background: "none", border: 0, cursor: "pointer", padding: 0 }}>
              Monitor →
            </button>
          </div>
          {data.agentsLoaded && sorted.length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "20px 12px" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/illustrations/spot-agents.svg" alt="" width={160} height={120} style={{ width: 160, height: "auto", borderRadius: 12 }} />
              <div style={{ fontWeight: 600, marginTop: 12 }}>No agents yet</div>
              <Link href={`${APP_ROUTES.agents}/new`} style={{ fontSize: 14, fontWeight: 500, textDecoration: "none", marginTop: 6 }}>
                Hire your first agent →
              </Link>
            </div>
          ) : null}
          {data.agentsFailed ? (
            <div style={{ fontSize: 14, color: "var(--gv-muted)", padding: "14px 8px" }}>Agents could not load. Refresh the page to try again.</div>
          ) : null}
          {!data.agentsLoaded && !data.agentsFailed ? (
            <div style={{ display: "grid", gap: 14, padding: "14px 8px" }}>
              <div className="gv-skel" style={{ width: "80%" }} />
              <div className="gv-skel" style={{ width: "65%" }} />
              <div className="gv-skel" style={{ width: "72%" }} />
            </div>
          ) : null}
          {sorted.slice(0, 5).map(({ agent, state }) => {
            const color = state === "exec" ? GREEN : state === "wait" ? AMBER : state === "fault" ? RED : GREY
            const text = state === "wait" ? "var(--gv-amber-text)" : state === "exec" ? "var(--gv-brand-strong)" : state === "fault" ? RED : "var(--gv-muted)"
            const label = state === "exec" ? "Executing" : state === "wait" ? "Waiting" : state === "fault" ? "Needs attention" : state === "paused" ? "Paused" : "Available"
            const active = state === "exec" || state === "wait"
            return (
              <Link key={agent.id} href={`${APP_ROUTES.agents}/${agent.id}`} className="gv-row" style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 8px", borderRadius: 10, borderTop: "1px solid var(--gv-subtle)" }}>
                <DepartmentIcon department={agent.department} size="md" title={`${label}`}>
                  <span aria-hidden style={{ position: "absolute", right: -2, bottom: -2, width: 11, height: 11, borderRadius: "50%", background: color, border: "2px solid var(--gv-card)" }} />
                </DepartmentIcon>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{agent.name}</div>
                  <div className="gv-mono" style={{ fontSize: 13, color: "var(--gv-muted)" }}>{agent.model || "auto"}</div>
                </div>
                <svg width="84" height="28" viewBox="0 0 84 28" aria-hidden className="gv-hide-sm">
                  <path d={active ? HEART_ACTIVE : HEART_IDLE} fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className={active ? "gv-heart" : undefined} />
                </svg>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 500, color: text, minWidth: 92, justifyContent: "flex-end" }}>
                  <span className={active ? "gv-ping" : undefined} style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: color }} />
                  {label}
                </span>
              </Link>
            )
          })}
          {sorted.length > 5 ? (
            <Link href={APP_ROUTES.agents} style={{ display: "block", fontSize: 14, fontWeight: 500, textDecoration: "none", padding: "12px 8px 0", borderTop: "1px solid var(--gv-subtle)" }}>
              All {sorted.length} agents →
            </Link>
          ) : null}
        </div>

        <div className="gv-card gv-rise" style={{ padding: 24, animationDelay: "380ms" }} data-dashboard-changes="">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>What changed</h3>
            <span style={{ fontSize: 13, color: "var(--gv-muted)" }}>Since yesterday</span>
          </div>
          {changes.length === 0 ? (
            <div style={{ fontSize: 14, color: "var(--gv-muted)" }}>No agent activity recorded yet.</div>
          ) : (
            <div style={{ position: "relative", paddingLeft: 26 }}>
              <div style={{ position: "absolute", left: 6, top: 6, bottom: 6, width: 2, background: "linear-gradient(var(--gv-mint-2), var(--gv-subtle))" }} />
              {changes.map((e, i) => (
                <Link key={e.id} href={e.href} className="gv-rise" style={{ display: "block", position: "relative", paddingBottom: 20, animationDelay: `${420 + i * 90}ms`, color: "inherit", textDecoration: "none" }}>
                  <span style={{ position: "absolute", left: -26, top: 4, width: 14, height: 14, borderRadius: "50%", background: "var(--gv-card)", border: `2px solid ${e.color}` }} />
                  <div style={{ fontSize: 15, fontWeight: 500, lineHeight: 1.4 }}>{e.text}</div>
                  <div style={{ fontSize: 13, color: "var(--gv-muted)", marginTop: 3 }}>{e.meta}</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      <section style={{ marginTop: 40 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Start next</h3>
          <span style={{ fontSize: 14, color: "var(--gv-muted)" }}>Suggested from your workspace setup</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))", gap: 16 }}>
          {start.map((c, i) => {
            const inner = (
              <>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: c.tint, display: "grid", placeItems: "center" }}>
                  <StartIcon icon={c.icon} stroke={c.stroke} />
                </div>
                <div style={{ fontWeight: 600, marginTop: 14 }}>{c.title}</div>
                <div style={{ fontSize: 14, color: "var(--gv-muted)", marginTop: 4, lineHeight: 1.5 }}>{c.body}</div>
              </>
            )
            return c.href === "#reports" ? (
              <button key={c.id} type="button" onClick={onOpenReports} className="gv-card gv-rise gv-start" style={{ animationDelay: `${420 + i * 50}ms`, textAlign: "left", font: "inherit", cursor: "pointer" }}>
                {inner}
              </button>
            ) : (
              <Link key={c.id} href={c.href} className="gv-card gv-rise gv-start" style={{ animationDelay: `${420 + i * 50}ms` }}>
                {inner}
              </Link>
            )
          })}
        </div>
      </section>
    </div>
  )
}
