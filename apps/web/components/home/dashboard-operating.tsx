"use client"

import Link from "next/link"
import { ArrowRight, Plus } from "lucide-react"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { AskPromptChips } from "@/components/gravitre/ask-prompt-chips"
import { resolveKpiValue } from "@/components/home/dashboard-widget-view"
import { KPI_BY_ID } from "@/lib/dashboard/kpi-registry"
import { APP_ROUTES } from "@/lib/app-routes"
import { relativeTime } from "@/lib/agent-job-result"
import { cn } from "@/lib/utils"
import type { DashboardWidget } from "@/lib/dashboard/types"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"
import type { RoleQuickAction } from "@/lib/role-quick-actions"

const WORKING = new Set(["active", "processing", "running"])

function statusLabel(status: string): string {
  if (status === "processing" || status === "running") return "Executing"
  if (status === "active") return "Active"
  if (status === "error") return "Needs attention"
  return "Idle"
}

/** Operating summary for the page header status line — counts only from loaded data. */
export function dashboardStatusLine(data: HomeDashboardData): { text: string; tone: "live" | "idle" | "attention" } {
  const parts: string[] = []
  if (data.agentTotal != null) {
    parts.push(`${data.activeAgents ?? 0} of ${data.agentTotal} agents working`)
  }
  if (data.pendingApprovals > 0) {
    parts.push(`${data.pendingApprovals} waiting on you`)
  }
  if (data.metrics.totalRuns != null) {
    parts.push(`${data.metrics.totalRuns} runs in range`)
  }
  const tone = data.pendingApprovals > 0 || (data.agentStatusCounts?.error ?? 0) > 0
    ? "attention"
    : (data.activeAgents ?? 0) > 0
      ? "live"
      : "idle"
  return { text: parts.length > 0 ? parts.join(" · ") : "Waiting for workspace activity", tone }
}

/** The digital workforce, ordered by who is working now. */
export function WorkforceStrip({ data }: { data: HomeDashboardData }) {
  const ordered = [...data.agents].sort((a, b) => {
    const rank = (s: string) => (s === "error" ? 0 : WORKING.has(s) ? 1 : 2)
    return rank(String(a.status ?? "").toLowerCase()) - rank(String(b.status ?? "").toLowerCase())
  })
  const shown = ordered.slice(0, 6)

  return (
    <section aria-labelledby="dashboard-workforce" className="space-y-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="dashboard-workforce" className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">
          Your workforce
        </h2>
        <Link
          href={APP_ROUTES.agents}
          className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          {data.agentTotal != null ? `All ${data.agentTotal} agents` : "Agents"}
          <ArrowRight className="size-3" aria-hidden />
        </Link>
      </div>
      {shown.length === 0 ? (
        <Link
          href={`${APP_ROUTES.agents}/new`}
          className="flex items-center gap-3 rounded-[12px] border border-dashed border-[color:var(--g-border-default)] px-4 py-4 text-left transition-colors hover:bg-[color:var(--g-surface-1)]"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-[9px] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
            <Plus className="size-4" aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-[13px] font-medium text-foreground">Hire your first agent</span>
            <span className="block text-xs text-muted-foreground">
              Agents you create appear here with what they are working on.
            </span>
          </span>
        </Link>
      ) : (
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((agent) => {
            const status = String(agent.status ?? "idle").toLowerCase()
            const working = WORKING.has(status)
            return (
              <li key={agent.id} className="min-w-0">
                <Link
                  href={`${APP_ROUTES.agents}/${agent.id}`}
                  className="group flex h-full min-w-0 flex-col gap-2.5 rounded-[12px] border border-[color:var(--g-border-default)] bg-card p-3 transition-[border-color,box-shadow] hover:border-[color:var(--g-border-strong)] hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <AgentIdentityAvatar agent={agent} size="sm" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-semibold text-foreground">{agent.name}</span>
                      <span className="block truncate text-[11.5px] text-muted-foreground">
                        {agent.role || agent.department || "Agent"}
                      </span>
                    </span>
                  </span>
                  <span className="flex min-w-0 items-center justify-between gap-2 text-[11.5px]">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 font-medium",
                        working && "text-[color:var(--g-brand)]",
                        status === "error" && "text-destructive",
                        !working && status !== "error" && "text-muted-foreground",
                      )}
                    >
                      <span
                        className={cn(
                          "size-1.5 rounded-full",
                          working && "bg-[color:var(--g-brand)]",
                          status === "error" && "bg-destructive",
                          !working && status !== "error" && "bg-muted-foreground/50",
                        )}
                        aria-hidden
                      />
                      {statusLabel(status)}
                    </span>
                    <span className="truncate text-muted-foreground">
                      {agent.lastActionTime ? relativeTime(agent.lastActionTime) : agent.model?.trim() || ""}
                    </span>
                  </span>
                  {agent.lastAction ? (
                    <span className="line-clamp-1 border-t border-[color:var(--g-border-subtle)] pt-2 text-[11.5px] text-muted-foreground">
                      {agent.lastAction}
                    </span>
                  ) : null}
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

/** Compact business-state rail — numbers from the configured KPI widgets. */
export function BusinessStateRail({
  data,
  widgets,
  quickActions,
}: {
  data: HomeDashboardData
  widgets: DashboardWidget[]
  quickActions: RoleQuickAction[]
}) {
  return (
    <aside className="space-y-5 lg:sticky lg:top-4" aria-label="Business state">
      <section aria-labelledby="dashboard-state" className="rounded-[14px] bg-[color:var(--g-rail-bg)] p-4 ring-1 ring-[color:var(--g-border-subtle)]">
        <h2 id="dashboard-state" className="text-[13px] font-semibold text-foreground">
          Business state
        </h2>
        {widgets.length === 0 ? (
          <p className="mt-2 text-xs text-muted-foreground">Add KPIs with Customize.</p>
        ) : (
          <dl className="mt-2 divide-y divide-[color:var(--g-border-subtle)]">
            {widgets.map((widget) => {
              const def = KPI_BY_ID[widget.metricId]
              const resolved = resolveKpiValue(widget.metricId, data)
              const label = widget.title ?? def?.name ?? widget.metricId
              const row = (
                <>
                  <dt className="min-w-0 truncate text-[12.5px] text-muted-foreground">{label}</dt>
                  <dd
                    className={cn(
                      "shrink-0 text-[15px] font-semibold tabular-nums text-foreground",
                      resolved.warning && "text-warning",
                      resolved.empty && "text-muted-foreground",
                    )}
                  >
                    {resolved.value}
                  </dd>
                </>
              )
              return resolved.href ? (
                <Link
                  key={widget.id}
                  href={resolved.href}
                  className="-mx-2 flex items-center justify-between gap-3 rounded-[8px] px-2 py-2 transition-colors hover:bg-[color:var(--g-surface-1)]"
                >
                  {row}
                </Link>
              ) : (
                <div key={widget.id} className="flex items-center justify-between gap-3 py-2">
                  {row}
                </div>
              )
            })}
          </dl>
        )}
      </section>

      <section aria-labelledby="dashboard-ask" className="space-y-2 px-1">
        <h2 id="dashboard-ask" className="text-[13px] font-semibold text-foreground">
          Ask about today
        </h2>
        <AskPromptChips
          layout="stack"
          prompts={[
            "What changed in my workspace since yesterday?",
            "Which workflows failed this week and why?",
            "What should I approve first?",
          ]}
        />
      </section>

      {quickActions.length > 0 ? (
        <section aria-labelledby="dashboard-next" className="space-y-1 px-1">
          <h2 id="dashboard-next" className="text-[13px] font-semibold text-foreground">
            Go to
          </h2>
          <ul>
            {quickActions.map((action) => (
              <li key={action.href}>
                <Link
                  href={action.href}
                  className="group flex items-center justify-between gap-2 rounded-[8px] px-2 py-1.5 text-[12.5px] text-foreground transition-colors hover:bg-[color:var(--g-surface-1)]"
                >
                  {action.label}
                  <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </aside>
  )
}
