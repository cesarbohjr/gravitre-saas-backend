"use client"

import Link from "next/link"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { AgentRoiRow } from "@/types/api"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import {
  UNASSIGNED_AGENT_ID,
  agentStatusLine,
  formatCount,
  formatHours,
  formatUsd,
  metricNumber,
  orderAgentRows,
  type ImpactPeriod,
} from "@/components/intelligence/impact/impact-model"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

type SnapshotAgent = IntelligencePageContextResponse["snapshot"]["agents"][number]

const TONE: Record<ReturnType<typeof agentStatusLine>["tone"], string> = {
  muted: "text-[color:var(--g-text-muted)]",
  danger: "text-[color:var(--g-danger)]",
  warning: "text-[color:var(--g-warning)]",
  live: "text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
}

export function ByAgentTable({
  rows,
  snapshotAgents,
  period,
  loading,
}: {
  rows: AgentRoiRow[]
  snapshotAgents: SnapshotAgent[]
  period: ImpactPeriod
  loading: boolean
}) {
  const byId = new Map(snapshotAgents.map((a) => [a.id, a]))
  const ordered = orderAgentRows(rows)

  return (
    <section
      aria-labelledby="impact-agents-heading"
      className="min-w-0 overflow-hidden rounded-[var(--np-radius-lg)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]"
    >
      <div className="flex items-center justify-between gap-3 border-b border-[color:var(--g-border-subtle)] px-5 py-4">
        <h2 id="impact-agents-heading" className={TYPE.cardTitle}>
          By agent
        </h2>
        <span className={TYPE.meta}>Last {period} days</span>
      </div>

      {loading && rows.length === 0 ? (
        <p className={cn(TYPE.bodyMuted, "px-5 py-6")}>Loading agents…</p>
      ) : ordered.length === 0 ? (
        <div className="px-5 py-6">
          <p className="text-sm font-medium text-[color:var(--g-text-primary)]">No agent activity in this period</p>
          <p className={cn(TYPE.meta, "mt-1")}>
            Rows appear when an agent runs or spends on model calls.{" "}
            <Link href={APP_ROUTES.agents} className="text-[color:var(--g-brand-active)] underline underline-offset-2 dark:text-[color:var(--g-brand)]">
              Open agents
            </Link>
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left">
            <thead>
              <tr className="border-b border-[color:var(--g-border-subtle)]">
                <th scope="col" className={cn(TYPE.tableHead, "px-5 py-3 font-normal")}>Agent</th>
                <th scope="col" className={cn(TYPE.tableHead, "px-3 py-3 font-normal")}>Tasks</th>
                <th scope="col" className={cn(TYPE.tableHead, "px-3 py-3 font-normal")}>Time saved</th>
                <th scope="col" className={cn(TYPE.tableHead, "px-3 py-3 font-normal")}>Revenue</th>
                <th scope="col" className={cn(TYPE.tableHead, "px-5 py-3 text-right font-normal")}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((row) => {
                const unassigned = row.agentId === UNASSIGNED_AGENT_ID
                const status = agentStatusLine(row, byId.get(row.agentId))
                const revenue = metricNumber(row.revenueInfluencedUsd)
                return (
                  <tr
                    key={row.agentId}
                    data-testid="impact-agent-row"
                    className={cn(
                      "border-b border-[color:var(--g-border-subtle)] last:border-b-0",
                      unassigned && "bg-[color:var(--g-approval-surface)]",
                    )}
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex min-w-0 flex-col">
                        {unassigned ? (
                          <span className="text-sm font-medium text-[color:var(--g-text-primary)]">Unassigned</span>
                        ) : (
                          <Link
                            href={`${APP_ROUTES.agents}/${encodeURIComponent(row.agentId)}`}
                            className="text-sm font-medium text-[color:var(--g-text-primary)] hover:underline"
                          >
                            {row.agentName}
                          </Link>
                        )}
                        <span className={cn("mt-0.5 text-xs", TONE[status.tone])}>{status.text}</span>
                      </div>
                    </td>
                    <td className={cn(TYPE.tableCell, "px-3 py-3.5 font-normal")}>
                      {formatCount(metricNumber(row.tasksCompleted))}
                    </td>
                    <td className={cn(TYPE.tableCell, "px-3 py-3.5 font-normal")}>
                      {formatHours(metricNumber(row.estimatedHoursSaved))}
                    </td>
                    <td
                      className={cn(
                        TYPE.tableCell,
                        "px-3 py-3.5 font-normal",
                        revenue == null && "text-[color:var(--g-text-muted)]",
                      )}
                    >
                      {formatUsd(revenue)}
                    </td>
                    <td className={cn(TYPE.tableCell, "px-5 py-3.5 text-right", unassigned ? "font-semibold" : "font-normal")}>
                      {formatUsd(metricNumber(row.agentCostUsd))}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <details className="group border-t border-[color:var(--g-border-subtle)] px-5 py-3.5">
        <summary className="cursor-pointer text-[13px] font-medium text-[color:var(--g-text-primary)] marker:text-[color:var(--g-text-muted)]">
          How these numbers are worked out
        </summary>
        <ul className={cn(TYPE.bodyMuted, "mt-3 list-disc space-y-1.5 pl-5")}>
          <li><strong className="font-medium text-[color:var(--g-text-primary)]">Tasks</strong> are counted directly from agent runs.</li>
          <li><strong className="font-medium text-[color:var(--g-text-primary)]">Cost</strong> is the measured spend on model calls.</li>
          <li><strong className="font-medium text-[color:var(--g-text-primary)]">Time saved</strong> is an estimate from task type and duration, not timed work.</li>
          <li><strong className="font-medium text-[color:var(--g-text-primary)]">Revenue</strong> only appears when a verified outcome carries a money value.</li>
          <li><strong className="font-medium text-[color:var(--g-text-primary)]">Return</strong> is estimated labor value divided by measured cost.</li>
        </ul>
        <AskGravitreSummonButton
          className="mt-2 px-0"
          label="Ask Gravitre about these numbers"
          prompt={`Explain my Impact numbers for the last ${period} days: what each agent cost, the tasks it finished, the time saved estimate and why revenue or return may show a dash.`}
        />
      </details>
    </section>
  )
}
