"use client"

import { useMemo, useState, type FormEvent } from "react"
import Link from "next/link"
import useSWR from "swr"
import { ArrowRight, CornerDownRight } from "lucide-react"
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

const LANE_ROLE: Record<FlowLaneId, { rule: string; count: string }> = {
  changed: { rule: "bg-[color:var(--g-border-strong)]", count: "text-muted-foreground" },
  needs: { rule: "bg-warning", count: "bg-warning/15 text-foreground" },
  running: { rule: "bg-[color:var(--g-brand)]", count: "bg-[color:var(--g-brand)]/12 text-foreground" },
  risk: { rule: "bg-destructive", count: "bg-destructive/12 text-foreground" },
  next: { rule: "bg-transparent", count: "text-muted-foreground" },
}

const INTERVENE_BAR: Record<NonNullable<FlowItem["tone"]>, string> = {
  attention: "before:bg-warning",
  fault: "before:bg-destructive",
  risk: "before:bg-warning",
  live: "before:bg-[color:var(--g-brand)]",
}

const ITEM_FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"

function ItemMeta({ item }: { item: FlowItem }) {
  if (!item.detail && !item.meta) return null
  return (
    <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-[11.5px] text-muted-foreground">
      {item.detail ? <span className="truncate">{item.detail}</span> : null}
      {item.detail && item.meta ? <span aria-hidden>·</span> : null}
      {item.meta ? <span className="shrink-0 tabular-nums">{item.meta}</span> : null}
    </span>
  )
}

/** Changed: a quiet timeline — context, not a call to action. */
function ChangedItem({ item }: { item: FlowItem }) {
  return (
    <li className="relative pl-5 before:absolute before:bottom-0 before:left-[9px] before:top-0 before:w-px before:bg-[color:var(--g-border-subtle)] first:before:top-4 last:before:bottom-auto last:before:h-4">
      <span aria-hidden className="absolute left-[6px] top-[15px] size-[7px] rounded-full border border-[color:var(--g-border-strong)] bg-background" />
      <Link href={item.href} className={cn("block rounded-[4px] px-2 py-2 transition-colors hover:bg-[color:var(--g-surface-1)]", ITEM_FOCUS)}>
        <span className="line-clamp-2 text-[12.5px] leading-snug text-foreground/85">{item.title}</span>
        <ItemMeta item={item} />
      </Link>
    </li>
  )
}

/** Needs you / At risk: intervention rows with an accent bar and an explicit verb. */
function InterveneItem({ item }: { item: FlowItem }) {
  return (
    <li>
      <Link
        href={item.href}
        data-intervene={item.tone}
        className={cn(
          "group relative flex items-start gap-2 rounded-[4px] bg-background py-2.5 pl-3.5 pr-2.5 shadow-[0_0_0_1px_var(--g-border-subtle)] transition-shadow before:absolute before:inset-y-1.5 before:left-1 before:w-[3px] before:rounded-full hover:shadow-[0_0_0_1px_var(--g-border-strong)]",
          item.tone ? INTERVENE_BAR[item.tone] : "before:bg-muted-foreground/40",
          ITEM_FOCUS,
        )}
      >
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 text-[13px] font-semibold leading-snug text-foreground">{item.title}</span>
          <ItemMeta item={item} />
        </span>
        {item.action ? (
          <span className="mt-px inline-flex shrink-0 items-center gap-0.5 rounded-[4px] px-1.5 py-0.5 text-[11.5px] font-medium text-foreground group-hover:bg-[color:var(--g-surface-1)]">
            {item.action}
            <ArrowRight className="size-3" aria-hidden />
          </span>
        ) : null}
      </Link>
    </li>
  )
}

/** Running: live work with a pulse marker. */
function RunningItem({ item }: { item: FlowItem }) {
  return (
    <li>
      <Link href={item.href} className={cn("flex items-start gap-2.5 rounded-[4px] px-2 py-2 transition-colors hover:bg-[color:var(--g-surface-1)]", ITEM_FOCUS)}>
        {item.agent ? (
          <span className="relative shrink-0">
            <AgentIdentityAvatar agent={item.agent} size="sm" />
          </span>
        ) : (
          <span aria-hidden className="relative mt-1.5 flex size-2 shrink-0">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-[color:var(--g-brand)] opacity-50 motion-reduce:animate-none" />
            <span className="relative inline-flex size-2 rounded-full bg-[color:var(--g-brand)]" />
          </span>
        )}
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 text-[13px] font-medium leading-snug text-foreground">{item.title}</span>
          <ItemMeta item={item} />
        </span>
      </Link>
    </li>
  )
}

/** Next: launch actions. */
function NextItem({ item }: { item: FlowItem }) {
  return (
    <li>
      <Link
        href={item.href}
        className={cn(
          "group flex items-center justify-between gap-2 rounded-[4px] border border-dashed border-[color:var(--g-border-strong)] px-3 py-2 text-[13px] text-foreground transition-colors hover:border-solid hover:bg-[color:var(--g-surface-1)]",
          ITEM_FOCUS,
        )}
      >
        <span className="min-w-0 truncate">{item.title}</span>
        <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
      </Link>
    </li>
  )
}

function LaneItem({ item, lane }: { item: FlowItem; lane: FlowLaneId }) {
  if (lane === "changed") return <ChangedItem item={item} />
  if (lane === "needs" || lane === "risk") return <InterveneItem item={item} />
  if (lane === "running") return <RunningItem item={item} />
  return <NextItem item={item} />
}

function LaneAsk({ prompt, label }: { prompt: string; label: string }) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()
  return (
    <button
      type="button"
      data-ask-prompt=""
      onClick={() =>
        summonWorkspace({ presentation: "compact", composerText: prompt, submit: false, selected: pageContext.selected })
      }
      className="inline-flex items-center gap-1 rounded-[4px] px-1.5 py-0.5 text-[11.5px] font-medium text-muted-foreground transition-colors hover:bg-[color:var(--g-surface-1)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={`Ask Gravitre about ${label.toLowerCase()}`}
      title={prompt}
    >
      <CornerDownRight className="size-3" aria-hidden />
      Ask
    </button>
  )
}

function Lane({ lane, loading }: { lane: FlowLane; loading: boolean }) {
  const populated = !loading && lane.items.length > 0
  const intervene = populated && (lane.id === "needs" || lane.id === "risk")
  const role = LANE_ROLE[lane.id]
  return (
    <section
      aria-labelledby={`flow-${lane.id}`}
      data-flow-lane={lane.id}
      data-flow-populated={populated ? "" : undefined}
      className={cn(
        "relative flex h-full min-h-0 min-w-0 flex-col overflow-hidden",
        lane.id === "needs" && populated && "bg-warning/[0.045]",
        lane.id === "risk" && populated && "bg-destructive/[0.035]",
      )}
    >
      <span aria-hidden className={cn("absolute inset-x-0 top-0 h-[2px]", populated ? role.rule : "bg-transparent")} />
      <header className="flex items-center justify-between gap-2 px-3 pb-2 pt-3">
        <h2 id={`flow-${lane.id}`} className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
          {lane.label}
          {lane.id !== "next" ? (
            <span
              className={cn(
                "min-w-5 rounded-full px-1.5 text-center text-[11.5px] font-semibold tabular-nums leading-5",
                populated ? role.count : "text-muted-foreground",
              )}
            >
              {loading ? "—" : lane.items.length}
            </span>
          ) : null}
        </h2>
        <LaneAsk prompt={lane.ask} label={lane.label} />
      </header>
      {loading ? (
        <p className="px-3 py-2 text-xs text-muted-foreground">Loading…</p>
      ) : lane.items.length === 0 ? (
        <p className="px-3 py-2 text-xs text-muted-foreground">{lane.empty}</p>
      ) : (
        <ul className={cn("min-h-0 flex-1 overflow-y-auto px-2 pb-3 md:max-h-[360px] xl:max-h-[440px]", intervene || lane.id === "next" ? "space-y-1.5" : "space-y-0.5")}>
          {lane.items.map((item) => (
            <LaneItem key={item.id} item={item} lane={lane.id} />
          ))}
        </ul>
      )}
    </section>
  )
}

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

export function useFlowAssignments() {
  const { user } = useAuth()
  return useSWR<DemoAssignment[]>(user ? ASSIGNMENTS_REFRESH_KEY : null, fetchAssignmentList, {
    revalidateOnFocus: true,
    refreshInterval: 30_000,
  })
}

export function OperatingFlow({
  data,
  quickActions,
  loading = false,
}: {
  data: HomeDashboardData
  quickActions: RoleQuickAction[]
  loading?: boolean
}) {
  const { data: assignments, isLoading: assignmentsLoading } = useFlowAssignments()
  const lanes = useMemo(() => buildFlowLanes(data, assignments, quickActions), [data, assignments, quickActions])
  const firstActive = lanes.find((lane) => lane.id === "needs" && lane.items.length > 0)?.id ?? "running"
  const [mobileLane, setMobileLane] = useState<FlowLaneId | null>(null)
  const activeMobile = mobileLane ?? firstActive
  const laneLoading = (id: FlowLaneId) => loading || (assignmentsLoading && (id === "running" || id === "risk"))

  return (
    <div data-operating-flow="" className="flex flex-col">
      {/* Phones: one lane at a time, chosen from a lane switcher */}
      <div className="md:hidden">
        <div role="tablist" aria-label="Operation lanes" className="flex overflow-x-auto border-b border-[color:var(--g-border-subtle)] px-2 scrollbar-none">
          {lanes.map((lane) => (
            <button
              key={lane.id}
              type="button"
              role="tab"
              aria-selected={activeMobile === lane.id}
              onClick={() => setMobileLane(lane.id)}
              className={cn(
                "relative shrink-0 px-3 py-2.5 text-[13px] font-medium",
                activeMobile === lane.id
                  ? "text-foreground after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-[color:var(--g-text-primary)]"
                  : "text-muted-foreground",
              )}
            >
              {lane.label}
              {lane.id !== "next" && lane.items.length > 0 ? (
                <span className="ml-1 tabular-nums text-muted-foreground">{lane.items.length}</span>
              ) : null}
            </button>
          ))}
        </div>
        {lanes
          .filter((lane) => lane.id === activeMobile)
          .map((lane) => (
            <Lane key={lane.id} lane={lane} loading={laneLoading(lane.id)} />
          ))}
      </div>

      {/* Tablet and desktop: the full flow, lanes side by side */}
      <div
        data-flow-height="content"
        className="hidden min-h-[168px] grid-rows-1 divide-x divide-[color:var(--g-border-subtle)] overflow-x-auto border-b border-[color:var(--g-border-subtle)] md:grid"
        style={{ gridTemplateColumns: flowColumnTemplate(lanes, laneLoading) }}
      >
        {lanes.map((lane) => (
          <Lane key={lane.id} lane={lane} loading={laneLoading(lane.id)} />
        ))}
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
        className="h-9 min-w-0 flex-1 rounded-[6px] border border-[color:var(--g-border-strong)] bg-background px-3 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-[color:var(--g-text-primary)] focus:shadow-[0_0_0_1px_var(--g-text-primary)] focus:outline-none"
      />
    </form>
  )
}
