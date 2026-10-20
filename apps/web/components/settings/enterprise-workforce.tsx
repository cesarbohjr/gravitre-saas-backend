"use client"

/**
 * Enterprise > Workforce (design p18): completed agent tasks by team and agent
 * from GET /api/enterprise/insights/workforce?days=7|30, compared with the
 * period before. Counts only, no hours saved. The older operational signals
 * (GET /api/enterprise/workforce-analytics) stay below as their own card.
 */
import { useState } from "react"
import useSWR from "swr"
import { Bot, Users } from "lucide-react"
import { enterpriseApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import type { EnterpriseWorkforceAnalytics } from "@/types/api"
import { changeCopy, workforceKey, type WorkforceSummary } from "@/lib/settings-api/enterprise"
import { SetError, SetSkeleton, SetTabs } from "./settings-kit"

type Period = "7" | "30"

export function EnterpriseWorkforce() {
  const [period, setPeriod] = useState<Period>("30")
  const days = period === "7" ? 7 : 30
  const { data, error, isLoading, mutate } = useSWR<WorkforceSummary>(workforceKey(days), fetcher, {
    revalidateOnFocus: false,
    keepPreviousData: true,
  })
  const signals = useSWR<EnterpriseWorkforceAnalytics>("enterprise-workforce", () => enterpriseApi.getWorkforceAnalytics(), {
    revalidateOnFocus: false,
  })

  const change = data ? changeCopy(data.changePct, days) : null
  const teamMax = Math.max(1, ...(data?.byDepartment ?? []).map((t) => t.tasks))
  const idle = data?.departmentsIdle ?? []

  return (
    <>
      <div className="ent-intro">
        <p>Tasks agents completed, by team. Counts only, hours saved are not estimated.</p>
        <SetTabs<Period>
          label="Period"
          value={period}
          onChange={setPeriod}
          options={[
            { id: "7", label: "Last 7 days" },
            { id: "30", label: "Last 30 days" },
          ]}
        />
      </div>

      {error && !data ? (
        <section className="gs-card">
          <SetError message="Workforce data did not load." onRetry={() => void mutate()} />
        </section>
      ) : isLoading && !data ? (
        <section className="gs-card">
          <SetSkeleton rows={4} label="Loading workforce" />
        </section>
      ) : data ? (
        <>
          <div className="gs-minis">
            <div className="gs-mini">
              <div className="l">Tasks completed</div>
              <div className="v">{data.tasksCompleted.toLocaleString()}</div>
              <div className={`d ent-delta ${change?.tone ?? ""}`}>
                {change ? change.text : data.tasksCompleted > 0 ? "Nothing to compare with yet" : "None yet"}
              </div>
            </div>
            <div className="gs-mini">
              <div className="l">Active agents</div>
              <div className="v">{data.activeAgents.toLocaleString()}</div>
              <div className="d">
                {data.newAgents > 0 ? `${data.newAgents} new this period` : "No new agents this period"}
              </div>
            </div>
            <div className="gs-mini">
              <div className="l">Teams using agents</div>
              <div className="v">
                {data.departmentsTotal > 0 ? `${data.departmentsUsing} of ${data.departmentsTotal}` : "None yet"}
              </div>
              <div className="d">
                {data.departmentsTotal === 0
                  ? "No departments set up"
                  : idle.length === 0
                    ? "Every department"
                    : idle.length === 1
                      ? `${idle[0]} not yet`
                      : `${idle[0]} and ${idle.length - 1} more not yet`}
              </div>
            </div>
          </div>

          {data.tasksCompleted === 0 ? (
            <section className="gs-card">
              <div className="gs-empty">
                <Users size={22} aria-hidden />
                <b>No completed tasks in this period</b>
                <p>Counts appear here once agents finish tasks.</p>
              </div>
            </section>
          ) : (
            <div className="ent-grid2">
              <section className="gs-card ent-card">
                <h3 style={{ marginBottom: 12 }}>Tasks by team</h3>
                {data.byDepartment.map((team, i) => (
                  <div key={team.name} className="ent-team">
                    <span title={team.name}>{team.name}</span>
                    <span className="gs-track" role="presentation">
                      <span style={{ width: `${Math.round((team.tasks / teamMax) * 100)}%`, animationDelay: `${i * 70}ms` }} />
                    </span>
                    <span className="gs-mono" style={{ textAlign: "right" }}>
                      {team.tasks.toLocaleString()}
                    </span>
                  </div>
                ))}
              </section>
              <section className="gs-card ent-card">
                <h3 style={{ marginBottom: 6 }}>Busiest agents</h3>
                {data.busiestAgents.length === 0 ? (
                  <p className="gs-sub">None yet</p>
                ) : (
                  data.busiestAgents.map((agent) => (
                    <div key={agent.agentId} className="ent-agent">
                      <span className="gs-ico mute xs" aria-hidden>
                        <Bot size={15} aria-hidden />
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="n">{agent.name}</div>
                        <div className="d">{agent.department ?? "No department"}</div>
                      </div>
                      <span className="gs-mono" style={{ fontSize: 13 }}>
                        {agent.tasks.toLocaleString()}
                      </span>
                    </div>
                  ))
                )}
              </section>
            </div>
          )}
          {data.truncated ? <p className="gs-sub">Counts cover the most recent 20,000 tasks in this period.</p> : null}
        </>
      ) : null}

      <section className="gs-card ent-card">
        <h3>Operational signals</h3>
        <p className="ent-card-sub">All recorded agent jobs and audit events for this workspace</p>
        {signals.error && !signals.data ? (
          <SetError message="Operational signals did not load." onRetry={() => void signals.mutate()} />
        ) : !signals.data ? (
          <SetSkeleton rows={2} />
        ) : (
          <div className="gs-minis">
            {[
              ["Failed tasks", signals.data.tasksFailed.toLocaleString()],
              ["Running now", signals.data.tasksRunning.toLocaleString()],
              ["Agent handoffs", signals.data.handoffs.toLocaleString()],
              // toolSuccessRate is already a percentage (workforce_analytics_service).
              ["Tool success", `${Math.round(signals.data.toolSuccessRate ?? 0)}%`],
              ["Approval waits", signals.data.approvalWaitEvents.toLocaleString()],
              ["SLA breaches", signals.data.slaBreaches.toLocaleString()],
            ].map(([label, value]) => (
              <div key={label} className="gs-tile">
                <span>{label}</span>
                <b>{value}</b>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
