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
    })
  }
  for (const assignment of (assignments ?? []).filter((a) => a.status === "needs_approval").slice(0, 3)) {
    needs.push({
      id: `assignment-approval-${assignment.id}`,
      title: assignment.title,
      detail: `${assignment.agent.name} · waiting for your decision`,
      href: `/assignments/${assignment.id}?approval=1`,
      tone: "attention",
    })
  }
  for (const agent of data.agents.filter((a) => String(a.status ?? "").toLowerCase() === "error")) {
    needs.push({
      id: `agent-error-${agent.id}`,
      title: `${agent.name} stopped with an error`,
      detail: "Retry or reassign",
      href: `${APP_ROUTES.agents}/${agent.id}`,
      tone: "fault",
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
    risk.push({ id: `risk-${item.id}`, title: item.title, detail: item.summary, href: APP_ROUTES.revenueRisk, tone: "risk" })
  }
  for (const assignment of (assignments ?? []).filter((a) => a.status === "failed").slice(0, 4)) {
    risk.push({
      id: `failed-${assignment.id}`,
      title: assignment.title,
      detail: `Failed · ${assignment.agent.name}`,
      href: `/assignments/${assignment.id}`,
      tone: "fault",
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

const TONE_DOT: Record<NonNullable<FlowItem["tone"]>, string> = {
  attention: "bg-warning",
  fault: "bg-destructive",
  live: "bg-[color:var(--g-brand)]",
  risk: "bg-warning",
}

function LaneItem({ item, lane }: { item: FlowItem; lane: FlowLaneId }) {
  if (lane === "next") {
    return (
      <li>
        <Link
          href={item.href}
          className="group flex items-center justify-between gap-2 px-3 py-2.5 text-[13px] text-foreground transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          <span className="min-w-0 truncate">{item.title}</span>
          <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      </li>
    )
  }
  return (
    <li>
      <Link
        href={item.href}
        className={cn(
          "group flex gap-2.5 px-3 py-2.5 transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
          lane === "needs" && "bg-background",
        )}
      >
        {item.agent ? (
          <AgentIdentityAvatar agent={item.agent} size="sm" />
        ) : (
          <span aria-hidden className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", item.tone ? TONE_DOT[item.tone] : "bg-muted-foreground/40")} />
        )}
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 text-[13px] font-medium leading-snug text-foreground">{item.title}</span>
          {item.detail || item.meta ? (
            <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-[11.5px] text-muted-foreground">
              {item.detail ? <span className="truncate">{item.detail}</span> : null}
              {item.detail && item.meta ? <span aria-hidden>·</span> : null}
              {item.meta ? <span className="shrink-0 tabular-nums">{item.meta}</span> : null}
            </span>
          ) : null}
        </span>
      </Link>
    </li>
  )
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
  const emphasis = lane.id === "needs" && lane.items.length > 0
  return (
    <section
      aria-labelledby={`flow-${lane.id}`}
      data-flow-lane={lane.id}
      className={cn("flex h-full min-h-0 min-w-0 flex-col overflow-hidden", emphasis && "bg-[color:var(--g-surface-1)]")}
    >
      <header
        className={cn(
          "flex items-center justify-between gap-2 border-b px-3 py-2.5",
          emphasis ? "border-[color:var(--g-text-primary)]" : "border-[color:var(--g-border-subtle)]",
        )}
      >
        <h2 id={`flow-${lane.id}`} className="flex items-baseline gap-2 text-[13px] font-semibold text-foreground">
          {lane.label}
          {lane.id !== "next" ? (
            <span className={cn("text-[12px] tabular-nums", emphasis ? "text-foreground" : "text-muted-foreground")}>
              {loading ? "—" : lane.items.length}
            </span>
          ) : null}
        </h2>
        <LaneAsk prompt={lane.ask} label={lane.label} />
      </header>
      {loading ? (
        <p className="px-3 py-3 text-xs text-muted-foreground">Loading…</p>
      ) : lane.items.length === 0 ? (
        <p className="px-3 py-3 text-xs text-muted-foreground">{lane.empty}</p>
      ) : (
        <ul className="min-h-0 flex-1 divide-y divide-[color:var(--g-border-subtle)] overflow-y-auto">
          {lane.items.map((item) => (
            <LaneItem key={item.id} item={item} lane={lane.id} />
          ))}
        </ul>
      )}
    </section>
  )
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
      <div className="hidden h-[420px] auto-cols-[minmax(232px,1fr)] grid-flow-col grid-rows-1 divide-x lg:h-[max(360px,calc(100dvh-400px))] divide-[color:var(--g-border-subtle)] overflow-x-auto border-b border-[color:var(--g-border-subtle)] md:grid">
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
