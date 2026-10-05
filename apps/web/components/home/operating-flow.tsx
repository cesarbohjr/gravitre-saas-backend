"use client"

import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react"
import Link from "next/link"
import useSWR from "swr"
import { ArrowRight, Check, CornerDownRight } from "lucide-react"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { relativeTime } from "@/lib/agent-job-result"
import { ASSIGNMENTS_REFRESH_KEY, fetchAssignmentList } from "@/lib/assignments-list"
import type { DemoAssignment } from "@/lib/demo-assignments"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"
import type { RoleQuickAction } from "@/lib/role-quick-actions"
import { cn } from "@/lib/utils"

const WORKING = new Set(["active", "processing", "running"])

export type FlowLaneId = "changed" | "needs" | "running" | "risk" | "next"

type FlowItem = {
  id: string
  title: string
  detail?: string
  meta?: string
  href: string
  tone?: "attention" | "fault" | "live" | "risk"
  /** Verb for items that ask the operator to intervene. */
  action?: string
  agent?: HomeDashboardData["agents"][number]
  /** How many real records a grouped row stands for. */
  count?: number
}

type FlowLane = {
  id: FlowLaneId
  label: string
  empty: string
  ask: string
  items: FlowItem[]
}

/**
 * The operation as a left→right flow: what changed, what needs the operator,
 * what is running, what is at risk, what to start next. Every item is backed by
 * loaded data (agents, approvals, assignments, revenue risk); empty lanes say so.
 */
export function buildFlowLanes(
  data: HomeDashboardData,
  assignments: DemoAssignment[] | undefined,
  quickActions: RoleQuickAction[],
): FlowLane[] {
  const byRecent = [...data.agents]
    .filter((agent) => agent.lastAction)
    .sort((a, b) => String(b.lastActionTime ?? "").localeCompare(String(a.lastActionTime ?? "")))

  const changed: FlowItem[] = byRecent.slice(0, 6).map((agent) => ({
    id: `changed-${agent.id}`,
    title: String(agent.lastAction),
    meta: agent.lastActionTime ? relativeTime(agent.lastActionTime) : undefined,
    detail: agent.name,
    href: `${APP_ROUTES.agents}/${agent.id}`,
    agent,
  }))

  const needs: FlowItem[] = []
  const titled = data.pendingApprovalItems.filter((item) => item.title)
  for (const item of titled.slice(0, 4)) {
    needs.push({
      id: `approval-${item.id}`,
      title: String(item.title),
      detail: "Approval waiting on you",
      href: APP_ROUTES.approvals,
      tone: "attention",
      action: "Review",
    })
  }
  const untitled = data.pendingApprovals - Math.min(titled.length, 4)
  if (untitled > 0) {
    needs.push({
      id: "approvals-rest",
      title: `${untitled} ${titled.length > 0 ? "more " : ""}approval${untitled === 1 ? "" : "s"} waiting`,
      detail: "Review before agents continue",
      href: APP_ROUTES.approvals,
      tone: "attention",
      action: "Review",
      count: untitled,
    })
  }
  for (const assignment of (assignments ?? []).filter((a) => a.status === "needs_approval").slice(0, 3)) {
    needs.push({
      id: `assignment-approval-${assignment.id}`,
      title: assignment.title,
      detail: `${assignment.agent.name} · waiting for your decision`,
      href: `/assignments/${assignment.id}?approval=1`,
      tone: "attention",
      action: "Decide",
    })
  }
  for (const agent of data.agents.filter((a) => String(a.status ?? "").toLowerCase() === "error")) {
    needs.push({
      id: `agent-error-${agent.id}`,
      title: `${agent.name} stopped with an error`,
      detail: "Retry or reassign",
      href: `${APP_ROUTES.agents}/${agent.id}`,
      tone: "fault",
      action: "Open",
      agent,
    })
  }

  const running: FlowItem[] = []
  for (const assignment of (assignments ?? []).filter((a) => a.status === "running").slice(0, 5)) {
    running.push({
      id: `assignment-${assignment.id}`,
      title: assignment.title,
      detail: assignment.currentStepDetail?.trim() || assignment.agent.name,
      href: `/assignments/${assignment.id}`,
      tone: "live",
    })
  }
  for (const agent of data.agents.filter((a) => WORKING.has(String(a.status ?? "").toLowerCase())).slice(0, 6)) {
    running.push({
      id: `agent-${agent.id}`,
      title: agent.name,
      detail: agent.role || agent.department || "Agent",
      meta: agent.lastActionTime ? relativeTime(agent.lastActionTime) : undefined,
      href: `${APP_ROUTES.agents}/${agent.id}`,
      tone: "live",
      agent,
    })
  }

  const risk: FlowItem[] = []
  for (const item of data.revenueRisks.slice(0, 4)) {
    risk.push({ id: `risk-${item.id}`, title: item.title, detail: item.summary, href: APP_ROUTES.revenueRisk, tone: "risk", action: "Investigate" })
  }
  for (const assignment of (assignments ?? []).filter((a) => a.status === "failed").slice(0, 4)) {
    risk.push({
      id: `failed-${assignment.id}`,
      title: assignment.title,
      detail: assignment.blocker ? `${assignment.agent.name} · ${assignment.blocker}` : `Failed · ${assignment.agent.name}`,
      href: `/assignments/${assignment.id}`,
      tone: "fault",
      action: "Open",
    })
  }

  const next: FlowItem[] = [
    { id: "next-assign", title: "Assign work to an agent", href: "/assignments/new" },
    ...(data.agentTotal === 0 ? [{ id: "next-hire", title: "Hire your first agent", href: `${APP_ROUTES.agents}/new` }] : []),
    ...quickActions.map((action) => ({ id: `next-${action.href}`, title: action.label, href: action.href })),
  ]

  return [
    { id: "changed", label: "Changed", empty: "No agent activity recorded yet.", ask: "What changed in my workspace since yesterday?", items: changed },
    { id: "needs", label: "Needs you", empty: "Nothing is waiting on you.", ask: "What should I approve first?", items: needs },
    { id: "running", label: "Running", empty: "No work is running right now.", ask: "What is running right now, and is anything stuck?", items: running },
    { id: "risk", label: "At risk", empty: "No failures or revenue risks detected.", ask: "What is at risk in my operation this week?", items: risk },
    { id: "next", label: "Next", empty: "", ask: "What should I start next?", items: next },
  ]
}

const ITEM_FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"

/** Populated intervention lanes get the most room; empty lanes compress. */
export function flowColumnTemplate(lanes: FlowLane[], loading: (id: FlowLaneId) => boolean): string {
  return lanes
    .map((lane) => {
      if (loading(lane.id)) return "minmax(200px,1fr)"
      if (lane.id === "next") return "minmax(200px,0.85fr)"
      if (lane.items.length === 0) return "minmax(168px,0.6fr)"
      if (lane.id === "needs" || lane.id === "risk") return "minmax(248px,1.3fr)"
      return "minmax(224px,1fr)"
    })
    .join(" ")
}

export type WorkforceState = "executing" | "available" | "attention" | "paused"

/** Enabled, available, and executing are different facts; never collapse them into "active". */
export function workforceState(status: unknown): WorkforceState {
  const s = String(status ?? "").toLowerCase()
  if (s === "processing" || s === "running") return "executing"
  if (s === "error" || s === "failed") return "attention"
  if (s === "active" || s === "idle" || s === "ready") return "available"
  return "paused"
}

const STATE_ORDER: WorkforceState[] = ["executing", "attention", "available", "paused"]

export function workforceCapacity(agents: HomeDashboardData["agents"]) {
  const cells = agents
    .map((agent) => ({ id: agent.id, name: agent.name, state: workforceState(agent.status) }))
    .sort((a, b) => STATE_ORDER.indexOf(a.state) - STATE_ORDER.indexOf(b.state))
  const count = (state: WorkforceState) => cells.filter((cell) => cell.state === state).length
  const paused = count("paused")
  return {
    total: cells.length,
    enabled: cells.length - paused,
    executing: count("executing"),
    available: count("available"),
    attention: count("attention"),
    paused,
    cells,
  }
}

type BriefingPart = { text: string; tone?: "attention" | "fault" | "live" }

/** One sentence that reads the operation aloud. Built only from counted, loaded items. */
export function briefingSentence(lanes: FlowLane[], workforce: ReturnType<typeof workforceCapacity>): BriefingPart[][] {
  const needs = lanes.find((lane) => lane.id === "needs")?.items ?? []
  const risk = lanes.find((lane) => lane.id === "risk")?.items ?? []
  const decisions = needs.filter((item) => item.tone === "attention").reduce((sum, item) => sum + (item.count ?? 1), 0)
  const faults = needs.filter((item) => item.tone === "fault").length + risk.length
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

  const sentences: BriefingPart[][] = []
  if (decisions === 0 && faults === 0) sentences.push([{ text: "All clear." }, { text: " Nothing needs your decision." }])
  if (decisions > 0) {
    sentences.push([
      { text: plural(decisions, "decision", "decisions"), tone: "attention" },
      { text: decisions === 1 ? " is waiting on you." : " are waiting on you." },
    ])
  }
  if (faults > 0) {
    sentences.push([
      { text: plural(faults, "item", "items"), tone: "fault" },
      { text: faults === 1 ? " is failing or at risk." : " are failing or at risk." },
    ])
  }
  if (workforce.total === 0) {
    sentences.push([{ text: "No agents hired yet." }])
  } else {
    sentences.push([
      { text: plural(workforce.executing, "agent", "agents"), tone: workforce.executing > 0 ? "live" : undefined },
      { text: ` executing, ${workforce.available} available.` },
    ])
  }
  return sentences
}

function useFreshness(signal: unknown) {
  const [updatedAt, setUpdatedAt] = useState(() => Date.now())
  const [, setTick] = useState(0)
  useEffect(() => {
    setUpdatedAt(Date.now())
  }, [signal])
  useEffect(() => {
    const timer = window.setInterval(() => setTick((n) => n + 1), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const mins = Math.floor((Date.now() - updatedAt) / 60_000)
  return mins < 1 ? "just now" : mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`
}

const TONE_TEXT: Record<NonNullable<BriefingPart["tone"]>, string> = {
  attention: "text-warning",
  fault: "text-destructive",
  live: "text-[color:var(--g-brand)]",
}

const CELL: Record<WorkforceState, string> = {
  executing: "bg-[color:var(--g-brand)]",
  attention: "bg-destructive",
  available: "bg-muted-foreground/45",
  paused: "bg-[color:var(--g-border-default)]",
}

const STATE_LABEL: Record<WorkforceState, string> = {
  executing: "executing",
  attention: "needs attention",
  available: "available",
  paused: "paused or off",
}

/** The signature: every agent as a cell, colored by what it is actually doing. */
function WorkforcePulse({ workforce }: { workforce: ReturnType<typeof workforceCapacity> }) {
  if (workforce.total === 0) return null
  const shown = workforce.cells.slice(0, 60)
  return (
    <Link
      href={APP_ROUTES.agents}
      data-workforce-pulse=""
      className={cn("group -mx-1 block rounded-[6px] px-1 py-1.5", ITEM_FOCUS)}
      aria-label={`Workforce: ${workforce.executing} executing, ${workforce.available} available, ${workforce.attention} needing attention, ${workforce.enabled} of ${workforce.total} enabled. Open agents.`}
    >
      <span aria-hidden className="flex h-3 gap-[3px]">
        {shown.map((cell) => (
          <span
            key={cell.id}
            title={`${cell.name} · ${STATE_LABEL[cell.state]}`}
            className={cn("relative min-w-[5px] flex-1 overflow-hidden rounded-[2px]", CELL[cell.state])}
          >
            {cell.state === "executing" ? (
              <span className="g-trace-scan absolute inset-y-0 w-1/3 bg-background/45" />
            ) : null}
          </span>
        ))}
      </span>
      <span className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
        {(["executing", "attention", "available", "paused"] as const).map((state) =>
          workforce[state] > 0 ? (
            <span key={state} className="inline-flex items-center gap-1.5">
              <span aria-hidden className={cn("size-2 rounded-[2px]", CELL[state])} />
              <span className="tabular-nums text-foreground">{workforce[state]}</span> {STATE_LABEL[state]}
            </span>
          ) : null,
        )}
        <span className="inline-flex items-center gap-1 tabular-nums group-hover:text-foreground">
          {workforce.enabled} of {workforce.total} enabled
          <ArrowRight className="size-3.5" aria-hidden />
        </span>
      </span>
    </Link>
  )
}

/** Contextual prompts taken from the most urgent real item, so the user never re-explains context. */
function briefingPrompts(lanes: FlowLane[]): string[] {
  const lane = (id: FlowLaneId) => lanes.find((entry) => entry.id === id)?.items ?? []
  const prompts: string[] = []
  const decision = lane("needs").find((item) => item.tone === "attention" && !item.count)
  const fault = lane("needs").find((item) => item.tone === "fault") ?? lane("risk")[0]
  if (decision) prompts.push(`What happens if I approve "${decision.title}"?`)
  if (fault) prompts.push(`Why is "${fault.title}" failing, and how do I recover?`)
  if (lane("running").length > 0) prompts.push("Is any running work taking longer than expected?")
  prompts.push("What changed since yesterday?")
  return prompts.slice(0, 3)
}

function PromptChips({ prompts }: { prompts: string[] }) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Suggested questions">
      {prompts.map((prompt) => (
        <li key={prompt} className="min-w-0 max-w-full">
          <button
            type="button"
            data-ask-prompt=""
            onClick={() =>
              summonWorkspace({ presentation: "compact", composerText: prompt, submit: false, selected: pageContext.selected })
            }
            className="inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-full border border-[color:var(--g-border-default)] px-3.5 text-left text-[13px] text-muted-foreground transition-colors hover:border-[color:var(--g-border-strong)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <CornerDownRight className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">{prompt}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

function SectionHeading({ id, label, count, tone }: { id: string; label: string; count?: number; tone?: string }) {
  return (
    <h3 id={id} className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-foreground">
      {label}
      {count != null ? (
        <span className={cn("min-w-6 rounded-full px-2 text-center text-[13px] font-semibold tabular-nums leading-6", tone ?? "bg-[color:var(--g-surface-2)] text-muted-foreground")}>
          {count}
        </span>
      ) : null}
    </h3>
  )
}

function DecisionCard({ item }: { item: FlowItem }) {
  return (
    <li>
      <Link
        href={item.href}
        data-intervene={item.tone}
        className={cn(
          "group flex flex-col gap-3 rounded-[var(--np-radius-md)] border border-warning/35 bg-warning/[0.06] p-4 transition-colors hover:border-warning/60",
          ITEM_FOCUS,
        )}
      >
        <span className="min-w-0">
          <span className="line-clamp-2 text-[15px] font-semibold leading-snug text-foreground">{item.title}</span>
          {item.detail ? <span className="mt-1 block text-sm leading-relaxed text-muted-foreground">{item.detail}</span> : null}
        </span>
        <span className="inline-flex min-h-11 items-center gap-1.5 self-start rounded-[6px] bg-foreground px-4 text-sm font-medium text-background">
          {item.action ?? "Review"}
          <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </span>
      </Link>
    </li>
  )
}

function FaultRow({ item }: { item: FlowItem }) {
  return (
    <li>
      <Link
        href={item.href}
        data-intervene={item.tone}
        className={cn(
          "group flex min-h-14 items-start gap-3 rounded-[var(--np-radius-md)] border border-destructive/30 px-3.5 py-3 transition-colors hover:border-destructive/55",
          ITEM_FOCUS,
        )}
      >
        <span aria-hidden className={cn("mt-1.5 size-2 shrink-0 rounded-full", item.tone === "risk" ? "bg-warning" : "bg-destructive")} />
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">{item.title}</span>
          {item.detail ? <span className="mt-0.5 line-clamp-2 block text-[13px] leading-relaxed text-muted-foreground">{item.detail}</span> : null}
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 pt-px text-[13px] font-medium text-foreground">
          {item.action ?? "Open"}
          <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </span>
      </Link>
    </li>
  )
}

function LiveRow({ item }: { item: FlowItem }) {
  return (
    <li>
      <Link
        href={item.href}
        className={cn(
          "relative flex min-h-14 items-center gap-3 overflow-hidden rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] px-3.5 py-2.5 transition-colors hover:border-[color:var(--g-border-strong)]",
          ITEM_FOCUS,
        )}
      >
        <span className="relative shrink-0">
          {item.agent ? (
            <AgentIdentityAvatar agent={item.agent} size="sm" />
          ) : (
            <span aria-hidden className="flex size-8 items-center justify-center rounded-[6px] bg-[color:var(--g-brand)]/12">
              <span className="relative flex size-2">
                <span className="g-live-ping absolute inline-flex size-full rounded-full bg-[color:var(--g-brand)] opacity-60" />
                <span className="relative inline-flex size-2 rounded-full bg-[color:var(--g-brand)]" />
              </span>
            </span>
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">{item.title}</span>
          {item.detail || item.meta ? (
            <span className="block truncate text-[13px] text-muted-foreground">
              {[item.detail, item.meta].filter(Boolean).join(" · ")}
            </span>
          ) : null}
        </span>
        <span aria-hidden className="absolute inset-x-0 bottom-0 h-px overflow-hidden bg-[color:var(--g-brand)]/15">
          <span className="g-trace-scan absolute inset-y-0 w-1/3 bg-[color:var(--g-brand)]" />
        </span>
      </Link>
    </li>
  )
}

function ChangedTimeline({ items }: { items: FlowItem[] }) {
  return (
    <ol className="flex flex-col">
      {items.slice(0, 5).map((item) => (
        <li
          key={item.id}
          className="relative pl-5 before:absolute before:bottom-0 before:left-[5px] before:top-0 before:w-px before:bg-[color:var(--g-border-subtle)] first:before:top-4 last:before:bottom-auto last:before:h-4"
        >
          <span aria-hidden className="absolute left-[2px] top-[15px] size-[7px] rounded-full border border-[color:var(--g-border-strong)] bg-background" />
          <Link href={item.href} className={cn("block rounded-[4px] px-2 py-2 transition-colors hover:bg-[color:var(--g-surface-1)]", ITEM_FOCUS)}>
            <span className="line-clamp-2 text-sm leading-snug text-foreground/90">{item.title}</span>
            <span className="mt-0.5 block truncate text-[13px] text-muted-foreground">
              {[item.detail, item.meta].filter(Boolean).join(" · ")}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  )
}

function LoadingRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading">
      <span className="h-14 animate-pulse rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-1)] motion-reduce:animate-none" />
      <span className="h-14 animate-pulse rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-1)] motion-reduce:animate-none" />
    </div>
  )
}

export function useFlowAssignments() {
  const { user } = useAuth()
  return useSWR<DemoAssignment[]>(user ? ASSIGNMENTS_REFRESH_KEY : null, fetchAssignmentList, {
    revalidateOnFocus: true,
    refreshInterval: 30_000,
  })
}

/**
 * Operating overview, attention first: a spoken briefing over a live workforce pulse,
 * then only the sections that have something in them. Empty sections collapse to one line.
 */
export function OperatingFlow({
  data,
  quickActions,
  loading = false,
  ask,
}: {
  data: HomeDashboardData
  quickActions: RoleQuickAction[]
  loading?: boolean
  ask?: ReactNode
}) {
  const { data: assignments, isLoading: assignmentsLoading } = useFlowAssignments()
  const lanes = useMemo(() => buildFlowLanes(data, assignments, quickActions), [data, assignments, quickActions])
  const workforce = useMemo(() => workforceCapacity(data.agents), [data.agents])
  const freshness = useFreshness(assignments ?? data.agents)
  const lane = (id: FlowLaneId) => lanes.find((entry) => entry.id === id)!
  const laneLoading = (id: FlowLaneId) => loading || (assignmentsLoading && (id === "running" || id === "risk" || id === "needs"))

  const decisions = lane("needs").items.filter((item) => item.tone === "attention")
  const faults = [...lane("needs").items.filter((item) => item.tone === "fault"), ...lane("risk").items]
  const running = lane("running").items
  const changed = lane("changed").items
  const clear = [
    !laneLoading("needs") && decisions.length === 0 ? "nothing needs your decision" : null,
    !laneLoading("risk") && faults.length === 0 ? "nothing failing" : null,
    !laneLoading("running") && running.length === 0 ? "nothing running" : null,
  ].filter(Boolean) as string[]

  return (
    <div data-operating-flow="" data-flow-height="content" className="flex flex-col">
      <section
        aria-labelledby="dashboard-briefing"
        data-dashboard-briefing=""
        className="flex flex-col gap-4 border-b border-[color:var(--g-border-subtle)] px-[var(--np-page-pad-sm)] py-5 sm:px-[var(--np-page-pad)] lg:py-7"
      >
        <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
          <span aria-hidden className="relative flex size-2">
            <span className="g-live-ping absolute inline-flex size-full rounded-full bg-[color:var(--g-brand)] opacity-60" />
            <span className="relative inline-flex size-2 rounded-full bg-[color:var(--g-brand)]" />
          </span>
          Live · updated {freshness}
        </p>
        <h2 id="dashboard-briefing" className="max-w-3xl text-pretty text-[22px] font-semibold leading-snug tracking-[-0.02em] text-foreground sm:text-[28px]">
          {briefingSentence(lanes, workforce).map((sentence, index) => (
            <span key={index}>
              {index > 0 ? " " : null}
              {sentence.map((part, partIndex) => (
                <span key={partIndex} className={part.tone ? TONE_TEXT[part.tone] : index > 0 ? "text-foreground/70" : undefined}>
                  {part.text}
                </span>
              ))}
            </span>
          ))}
        </h2>
        <div className="max-w-3xl">
          <WorkforcePulse workforce={workforce} />
        </div>
        <div className="flex max-w-3xl flex-col gap-3">
          {ask}
          <PromptChips prompts={briefingPrompts(lanes)} />
        </div>
      </section>

      <div className="grid gap-8 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)] lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:gap-10">
        <div className="flex min-w-0 flex-col gap-7">
          {laneLoading("needs") ? (
            <LoadingRows />
          ) : decisions.length > 0 ? (
            <section aria-labelledby="flow-needs" data-flow-lane="needs" data-flow-populated="" className="flex flex-col gap-3">
              <SectionHeading id="flow-needs" label="Needs your decision" count={decisions.reduce((n, item) => n + (item.count ?? 1), 0)} tone="bg-warning/15 text-foreground" />
              <ul className="grid gap-3 md:grid-cols-2">
                {decisions.map((item) => (
                  <DecisionCard key={item.id} item={item} />
                ))}
              </ul>
            </section>
          ) : null}

          {faults.length > 0 ? (
            <section aria-labelledby="flow-risk" data-flow-lane="risk" data-flow-populated="" className="flex flex-col gap-3">
              <SectionHeading id="flow-risk" label="Failing or at risk" count={faults.length} tone="bg-destructive/15 text-foreground" />
              <ul className="flex flex-col gap-2">
                {faults.map((item) => (
                  <FaultRow key={item.id} item={item} />
                ))}
              </ul>
            </section>
          ) : null}

          {laneLoading("running") ? null : running.length > 0 ? (
            <section aria-labelledby="flow-running" data-flow-lane="running" data-flow-populated="" className="flex flex-col gap-3">
              <SectionHeading id="flow-running" label="Executing now" count={running.length} tone="bg-[color:var(--g-brand)]/15 text-foreground" />
              <ul className="flex flex-col gap-2">
                {running.map((item) => (
                  <LiveRow key={item.id} item={item} />
                ))}
              </ul>
            </section>
          ) : null}

          {clear.length > 0 ? (
            <p data-flow-clear="" className="flex items-start gap-2 text-sm leading-relaxed text-muted-foreground">
              <Check className="mt-0.5 size-4 shrink-0 text-[color:var(--g-brand)]" aria-hidden />
              <span>
                {clear.join(", ").replace(/^./, (c) => c.toUpperCase())}.
              </span>
            </p>
          ) : null}
        </div>

        <aside className="flex min-w-0 flex-col gap-7" aria-label="Recent changes and next steps">
          <section aria-labelledby="flow-changed" data-flow-lane="changed" className="flex flex-col gap-2">
            <SectionHeading id="flow-changed" label="What changed" />
            {loading ? (
              <LoadingRows />
            ) : changed.length > 0 ? (
              <ChangedTimeline items={changed} />
            ) : (
              <p className="text-sm text-muted-foreground">No agent activity recorded yet.</p>
            )}
          </section>
          <section aria-labelledby="flow-next" data-flow-lane="next" className="flex flex-col gap-3">
            <SectionHeading id="flow-next" label="Start next" />
            <ul className="flex flex-wrap gap-2">
              {lane("next").items.map((item) => (
                <li key={item.id}>
                  <Link
                    href={item.href}
                    className={cn(
                      "inline-flex min-h-11 items-center gap-1.5 rounded-full border border-[color:var(--g-border-default)] px-4 text-sm text-foreground transition-colors hover:border-[color:var(--g-border-strong)] hover:bg-[color:var(--g-surface-1)]",
                      ITEM_FOCUS,
                    )}
                  >
                    {item.title}
                    <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}

/** Operating command line: stages a question in the canonical workspace. Never auto-submits. */
export function OperatingAskLine({ className }: { className?: string }) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()
  const [text, setText] = useState("")
  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    const value = text.trim()
    summonWorkspace({
      presentation: "compact",
      composerText: value || undefined,
      submit: false,
      selected: pageContext.selected,
    })
    setText("")
  }
  return (
    <form onSubmit={onSubmit} className={cn("flex min-w-0 items-center", className)} role="search" aria-label="Ask Gravitre about this operation">
      <label htmlFor="operating-ask" className="sr-only">
        Ask Gravitre about today&apos;s operation
      </label>
      <input
        id="operating-ask"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Ask about today’s operation…"
        className="h-11 min-w-0 flex-1 rounded-[6px] border border-[color:var(--g-border-strong)] bg-background px-3 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-[color:var(--g-text-primary)] focus:shadow-[0_0_0_1px_var(--g-text-primary)] focus:outline-none"
      />
      <button type="submit" className="ml-2 min-h-11 rounded px-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Open draft</button>
    </form>
  )
}
