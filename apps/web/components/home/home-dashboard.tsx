"use client"

/**
 * Home dashboard (Gravitre Dashboard Redesign v3): AI Native briefing and the Reports board.
 * Every section reads live workspace data; empty sections say so with the illustration
 * the design library assigns to that state.
 */

import { useState } from "react"
import useSWR from "swr"
import "@/components/home/v3/home-v3.css"
import { AiNativeView, type AiNativeData, type PendingApproval } from "@/components/home/v3/ai-native-view"
import { ReportsControls, ReportsView } from "@/components/home/v3/reports-view"
import { PlayOutcomes } from "@/components/home/v3/play-outcomes"
import { useFlowAssignments } from "@/components/home/operating-flow"
import { agentsApi, approvalsApi, metricsApi, settingsApi } from "@/lib/api"
import { normalizeMetricsOverview } from "@/lib/dashboard/normalize-metrics"
import { useDashboardView, type DashboardView } from "@/lib/dashboard/view-preference"
import { useHomeReportsData, useHomeReportsLayout } from "@/hooks/use-home-reports"

const QUIET = { revalidateOnFocus: false, shouldRetryOnError: false } as const

function readApproval(raw: Record<string, unknown>): PendingApproval {
  const ctx = (raw.context && typeof raw.context === "object" ? raw.context : {}) as Record<string, unknown>
  const title =
    String(raw.title ?? "").trim() ||
    String(raw.workflow_name ?? raw.workflowName ?? "").trim() ||
    "Approval waiting"
  return {
    id: String(raw.id),
    title,
    description: typeof raw.description === "string" ? raw.description : null,
    action: typeof ctx.action === "string" ? ctx.action : null,
    requestedByName:
      typeof raw.requested_by_name === "string" ? raw.requested_by_name : typeof raw.requestedBy === "string" ? raw.requestedBy : null,
    requestedAt:
      typeof raw.requested_at === "string" ? raw.requested_at : typeof raw.requestedAt === "string" ? raw.requestedAt : null,
  }
}

function useAiNativeData(enabled: boolean, hasCustomReports: boolean) {
  const agents = useSWR(enabled ? "home/agents-list" : null, () => agentsApi.list(), QUIET)
  const approvals = useSWR(enabled ? "home/approvals" : null, () => approvalsApi.list(), { revalidateOnFocus: true, refreshInterval: 30_000 })
  const overview = useSWR(enabled ? "home/metrics-overview:7d" : null, () => metricsApi.overview("7d"), QUIET)
  const policies = useSWR(enabled ? "home/hitl-policies" : null, () => settingsApi.listHitlPolicies(), QUIET)
  const assignments = useFlowAssignments()
  const metrics = overview.data ? normalizeMetricsOverview(overview.data) : null

  const pending = (approvals.data?.approvals ?? []).filter((a) => String(a.status ?? "pending") === "pending")
  const data: AiNativeData = {
    agents: agents.data?.agents ?? [],
    agentsLoaded: Boolean(agents.data) || Boolean(agents.error),
    approvals: pending.map((a) => readApproval(a as unknown as Record<string, unknown>)),
    assignments: assignments.data,
    runsThisWeek: metrics ? metrics.totalRuns ?? 0 : null,
    activeConnectors: metrics ? metrics.activeConnectors ?? 0 : null,
    approvalPolicies: policies.data ? (policies.data.policies ?? []).length : null,
    hasCustomReports,
  }
  const refresh = () => {
    void approvals.mutate()
    void assignments.mutate()
    void agents.mutate()
  }
  return { data, refresh }
}

type HomeDashboardProps = {
  enabled: boolean
  orgId: string | null
  userId: string | null
  userName: string | null
}

export function HomeDashboard({ enabled, orgId, userId, userName }: HomeDashboardProps) {
  const [view, setView] = useDashboardView()
  const [editing, setEditing] = useState(false)
  const [showLibrary, setShowLibrary] = useState(false)
  const reportsLayout = useHomeReportsLayout(orgId, userId)
  const ai = useAiNativeData(enabled, reportsLayout.customized)
  const showReports = view === "reports"
  const reports = useHomeReportsData(enabled && showReports, reportsLayout.range)

  const changeView = (next: DashboardView) => {
    if (next === "ai") {
      setEditing(false)
      setShowLibrary(false)
    }
    setView(next)
  }

  return (
    <div className="gv-home" data-composition="understand">
      <div className="gv-wrap">
        <div
          data-dashboard-command-strip=""
          style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", padding: "20px 0", borderBottom: "1px solid var(--gv-border)" }}
        >
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, letterSpacing: "-0.02em" }}>Dashboard</h1>
          <div
            role="group"
            aria-label="Dashboard view"
            data-dashboard-view-toggle=""
            style={{ display: "flex", border: "1px solid var(--gv-border)", background: "var(--gv-card)", borderRadius: 999, padding: 4 }}
          >
            {(["ai", "reports"] as const).map((id) => (
              <button
                key={id}
                type="button"
                className={`gv-seg${view === id ? " on" : ""}`}
                aria-pressed={view === id}
                onClick={() => changeView(id)}
              >
                {id === "ai" ? "AI Native" : "Reports"}
              </button>
            ))}
          </div>
          {showReports ? (
            <ReportsControls
              range={reportsLayout.range}
              setRange={reportsLayout.setRange}
              preset={reportsLayout.preset}
              setPreset={reportsLayout.setPreset}
              editing={editing}
              setEditing={(v) => {
                setEditing(v)
                if (!v) setShowLibrary(false)
              }}
              openLibrary={() => {
                setShowLibrary(true)
                setEditing(true)
              }}
              reset={reportsLayout.resetWidgets}
            />
          ) : (
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "var(--gv-muted)" }}>
              <span className="gv-ping" style={{ background: "#19C37D", width: 8, height: 8 }} /> Live · updated just now
            </div>
          )}
        </div>

        {showReports ? (
          <>
            {reports.error && !reports.data ? (
              <div className="gv-card" style={{ marginTop: 24, padding: 32, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 10 }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/illustrations/moment-error.svg" alt="" width={200} height={150} style={{ width: 200, height: "auto", borderRadius: 12 }} />
                <div style={{ fontWeight: 600 }}>Reports could not load</div>
                <div style={{ fontSize: 14, color: "var(--gv-muted)" }}>Refresh the page or try again in a moment.</div>
                <button type="button" className="gv-btn ghost" onClick={() => void reports.mutate()}>
                  Try again
                </button>
              </div>
            ) : (
              <ReportsView
                data={reports.data}
                error={reports.error}
                range={reportsLayout.range}
                preset={reportsLayout.preset}
                widgets={reportsLayout.widgets}
                setWidgets={reportsLayout.setWidgets}
                editing={editing}
                showLibrary={showLibrary}
                closeLibrary={() => setShowLibrary(false)}
                agents={ai.data.agents}
              />
            )}
            {editing ? null : <PlayOutcomes enabled={enabled} range={reportsLayout.range} />}
          </>
        ) : (
          <AiNativeView data={ai.data} userName={userName} onOpenReports={() => changeView("reports")} onDecided={ai.refresh} />
        )}
      </div>
    </div>
  )
}
