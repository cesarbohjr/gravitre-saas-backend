"use client"

import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { HomeDashboard } from "@/components/home/home-dashboard"
import { useAuth } from "@/lib/auth-context"
import {
  architectureAdminApi,
  intelligenceApi,
  approvalsApi,
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
  const { data: onboarding } = useSWR<OnboardingProgress>(
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
  const { data: approvalsData } = useSWR(
    user ? "home/approvals" : null,
    () => approvalsApi.list(),
    { revalidateOnFocus: false },
  )

  const roleId =
    roleFromOnboardingStepData(onboarding?.step_data) ??
    (WELCOME_ROLES[0]?.id as WelcomeRoleId)
  const roleMeta = WELCOME_ROLES.find((entry) => entry.id === roleId) ?? WELCOME_ROLES[0]

  const pendingApprovals = approvalsData?.approvals?.length ?? 0
  const revenueRisks = businessImpact?.revenueRiskItems ?? []
  const avgConfidence =
    typeof trust?.avg_confidence === "number"
      ? Math.round(trust.avg_confidence * 100)
      : typeof trust?.avgConfidence === "number"
        ? Math.round(trust.avgConfidence * 100)
        : null

  const mlActive = typeof aiOs?.ml_models_active === "number" ? aiOs.ml_models_active : null
  const memoriesCount = typeof aiOs?.memories_count === "number" ? aiOs.memories_count : null
  const showGettingStarted = !onboarding?.welcome_completed && !onboarding?.skipped

  return (
    <AppShell title="Home">
      <HomeDashboard
        roleLabel={roleMeta?.label ?? "there"}
        pendingApprovals={pendingApprovals}
        avgConfidence={avgConfidence}
        queryRows={learning?.queryRows ?? 0}
        queryRowsNeeded={learning?.queryRowsNeeded ?? 50}
        workflowRows={learning?.workflowRows ?? 0}
        workflowRowsNeeded={learning?.workflowRowsNeeded ?? 30}
        hasLearningSnapshot={Boolean(learning?.hasAnySnapshot)}
        mlActive={mlActive}
        memoriesCount={memoriesCount}
        revenueRisks={revenueRisks}
        predictiveSummary={
          typeof predictive?.summary === "string" ? predictive.summary : null
        }
        showGettingStarted={showGettingStarted}
      />
    </AppShell>
  )
}
