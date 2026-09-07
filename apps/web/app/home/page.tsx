"use client"

import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { HomeDashboard } from "@/components/home/home-dashboard"
import { Skeleton } from "@/components/ui/skeleton"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { useAuth } from "@/lib/auth-context"
import {
  architectureAdminApi,
  intelligenceApi,
  approvalsApi,
  metricsApi,
  agentsApi,
} from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import {
  roleFromOnboardingStepData,
  WELCOME_ROLES,
  type WelcomeRoleId,
} from "@/lib/welcome-flow"
import type { OnboardingProgress } from "@/types/api"

export default function HomePage() {
  const { user } = useAuth()
  const { data: onboarding, error: onboardingError, isLoading: onboardingLoading } = useSWR<OnboardingProgress>(
    user ? "/api/onboarding" : null,
    fetcher,
    { revalidateOnFocus: false },
  )
  const { data: learning } = useSWR(
    user ? "home/learning-progress" : null,
    () => intelligenceApi.learningProgress(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: trust } = useSWR(
    user ? "home/trust" : null,
    () => intelligenceApi.trustSummary({ periodDays: 7 }),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: businessImpact } = useSWR(
    user ? "home/business-impact" : null,
    () => intelligenceApi.businessImpact(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: aiOs } = useSWR(
    user ? "home/ai-os" : null,
    () => architectureAdminApi.aiOsStatus(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: predictive } = useSWR(
    user ? "home/predictive" : null,
    () => architectureAdminApi.predictiveOps(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: learningLive } = useSWR(
    user ? "home/learning-live" : null,
    () => intelligenceApi.learningLiveDashboard(),
    { revalidateOnFocus: false, shouldRetryOnError: false, refreshInterval: 30_000 },
  )
  const { data: learningStatus } = useSWR(
    user ? "home/learning-status" : null,
    () => architectureAdminApi.learningStatus(),
    { revalidateOnFocus: false, shouldRetryOnError: false, refreshInterval: 30_000 },
  )
  const { data: approvalsData } = useSWR(
    user ? "home/approvals" : null,
    () => approvalsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: metricsOverview } = useSWR(
    user ? "home/metrics-overview" : null,
    () => metricsApi.overview(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: agentsList } = useSWR(
    user ? "home/agents-list" : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  const roleId =
    roleFromOnboardingStepData(onboarding?.step_data) ??
    (WELCOME_ROLES[0]?.id as WelcomeRoleId)
  const roleMeta = WELCOME_ROLES.find((entry) => entry.id === roleId) ?? WELCOME_ROLES[0]

  const pendingApprovalItems =
    approvalsData?.approvals?.filter((item) => item.status === "pending") ?? []
  const pendingApprovals = pendingApprovalItems.length
  const revenueRisks = businessImpact?.revenueRiskItems ?? []
  const avgConfidence =
    typeof trust?.avg_confidence === "number"
      ? Math.round(trust.avg_confidence * 100)
      : typeof trust?.avgConfidence === "number"
        ? Math.round(trust.avgConfidence * 100)
        : null

  const mlActive = typeof aiOs?.ml_models_active === "number" ? aiOs.ml_models_active : null
  const memoriesCount = typeof aiOs?.memories_count === "number" ? aiOs.memories_count : null
  const aiSystemsOnline =
    typeof aiOs?.systems_online === "number"
      ? aiOs.systems_online
      : typeof aiOs?.ai_systems_online === "number"
        ? aiOs.ai_systems_online
        : null
  const lastLearningCycle =
    typeof aiOs?.last_learning_cycle === "string"
      ? aiOs.last_learning_cycle
      : typeof aiOs?.last_cycle_at === "string"
        ? aiOs.last_cycle_at
        : null
  const showGettingStarted = !onboarding?.welcome_completed && !onboarding?.skipped
  const showRoleQuickActions = showGettingStarted || !learning?.hasAnySnapshot

  const agents = agentsList?.agents ?? []
  const activeAgents = agents.filter((agent) => {
    const status = String(agent.status ?? "").toLowerCase()
    return status === "active" || status === "processing" || status === "running"
  }).length
  const agentStatusCounts = {
    active: agents.filter((a) => String(a.status ?? "").toLowerCase() === "active").length,
    idle: agents.filter((a) => String(a.status ?? "").toLowerCase() === "idle").length,
    processing: agents.filter((a) => {
      const s = String(a.status ?? "").toLowerCase()
      return s === "processing" || s === "running"
    }).length,
    error: agents.filter((a) => String(a.status ?? "").toLowerCase() === "error").length,
  }
  const totalRuns = metricsOverview?.total_runs ?? 0
  const successfulRuns = metricsOverview?.successful_runs ?? 0
  const successRate =
    totalRuns > 0 ? Math.round((successfulRuns / totalRuns) * 1000) / 10 : null
  const avgDurationMs =
    typeof metricsOverview?.avg_run_duration_ms === "number"
      ? metricsOverview.avg_run_duration_ms
      : null
  const runsByDay = metricsOverview?.runs_by_day ?? []

  return (
    <AppShell title="Dashboard">
      {onboardingLoading && user ? (
        <div className="space-y-4" aria-busy="true" aria-label="Loading home dashboard">
          <Skeleton className="h-10 w-64" />
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Skeleton className="h-36 rounded-xl" />
            <Skeleton className="h-36 rounded-xl" />
            <Skeleton className="h-36 rounded-xl" />
          </div>
        </div>
      ) : onboardingError && user ? (
        <WorkSectionErrorCard
          title="Could not load home dashboard"
          message="Refresh the page or try again in a moment."
        />
      ) : (
        <HomeDashboard
          roleId={roleId}
          roleLabel={roleMeta?.label ?? "there"}
          pendingApprovals={pendingApprovals}
          pendingApprovalItems={pendingApprovalItems.map((item) => ({
            id: item.id,
            title: item.workflow_name ?? item.workflowName ?? `Run ${item.id.slice(0, 8)}`,
          }))}
          avgConfidence={avgConfidence}
          queryRows={learning?.queryRows ?? 0}
          queryRowsNeeded={learning?.queryRowsNeeded ?? 50}
          workflowRows={learning?.workflowRows ?? 0}
          workflowRowsNeeded={learning?.workflowRowsNeeded ?? 30}
          hasLearningSnapshot={Boolean(learning?.hasAnySnapshot)}
          mlActive={mlActive}
          memoriesCount={memoriesCount}
          aiSystemsOnline={aiSystemsOnline}
          lastLearningCycle={lastLearningCycle}
          revenueRisks={revenueRisks}
          predictiveSummary={
            typeof predictive?.summary === "string" ? predictive.summary : null
          }
          readyModelCount={
            typeof learningLive?.ready_model_count === "number"
              ? learningLive.ready_model_count
              : null
          }
          learningVelocity={
            typeof learningStatus?.learning_velocity === "string"
              ? learningStatus.learning_velocity
              : null
          }
          showGettingStarted={showGettingStarted}
          showRoleQuickActions={showRoleQuickActions}
          activeAgents={agents.length > 0 ? activeAgents : null}
          agentTotal={agents.length > 0 ? agents.length : null}
          agentStatusCounts={agents.length > 0 ? agentStatusCounts : null}
          successRate={successRate}
          avgDurationMs={avgDurationMs}
          runsByDay={runsByDay}
          activeWorkflows={
            typeof metricsOverview?.active_workflows === "number"
              ? metricsOverview.active_workflows
              : null
          }
        />
      )}
    </AppShell>
  )
}
