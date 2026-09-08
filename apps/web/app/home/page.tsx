"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { HomeDashboard } from "@/components/home/home-dashboard"
import { Skeleton } from "@/components/ui/skeleton"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { useAuth } from "@/lib/auth-context"
import { fetcher } from "@/lib/fetcher"
import { ensureSelectedOrg, getQuickOrgId } from "@/lib/org-context"
import {
  roleFromOnboardingStepData,
  WELCOME_ROLES,
  type WelcomeRoleId,
} from "@/lib/welcome-flow"
import type { OnboardingProgress } from "@/types/api"
import { useHomeDashboardData } from "@/hooks/use-home-dashboard-data"
import { useDashboardLayout } from "@/hooks/use-dashboard-layout"

export default function HomePage() {
  const { user } = useAuth()
  const [orgId, setOrgId] = useState<string | null>(() => getQuickOrgId())

  useEffect(() => {
    if (user) void ensureSelectedOrg(true).then(setOrgId)
  }, [user])

  const { data: onboarding, error: onboardingError, isLoading: onboardingLoading } =
    useSWR<OnboardingProgress>(user ? "/api/onboarding" : null, fetcher, {
      revalidateOnFocus: false,
    })

  const layoutApi = useDashboardLayout(orgId, user?.id ?? null)
  const data = useHomeDashboardData(Boolean(user), layoutApi.layout.globalRange)

  const roleId =
    roleFromOnboardingStepData(onboarding?.step_data) ??
    (WELCOME_ROLES[0]?.id as WelcomeRoleId)
  const roleMeta = WELCOME_ROLES.find((entry) => entry.id === roleId) ?? WELCOME_ROLES[0]

  const showGettingStarted = !onboarding?.welcome_completed && !onboarding?.skipped
  const showRoleQuickActions = showGettingStarted || !data.hasLearningSnapshot

  return (
    <AppShell title="Dashboard">
      {onboardingLoading && user ? (
        <div className="space-y-3 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)]" aria-busy="true" aria-label="Loading home dashboard">
          <Skeleton className="h-9 w-48" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Skeleton className="h-24 rounded-[var(--np-radius-lg)]" />
            <Skeleton className="h-24 rounded-[var(--np-radius-lg)]" />
            <Skeleton className="h-24 rounded-[var(--np-radius-lg)]" />
            <Skeleton className="h-24 rounded-[var(--np-radius-lg)]" />
          </div>
          <Skeleton className="h-48 rounded-[var(--np-radius-lg)]" />
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
          showGettingStarted={showGettingStarted}
          showRoleQuickActions={showRoleQuickActions}
          data={data}
          editMode={layoutApi.editMode}
          setEditMode={layoutApi.setEditMode}
          globalRange={layoutApi.layout.globalRange}
          setRange={layoutApi.setRange}
          widgets={layoutApi.layout.widgets}
          displayedMetricIds={layoutApi.displayedMetricIds}
          addWidget={layoutApi.addWidget}
          removeWidget={layoutApi.removeWidget}
          reorderWidget={layoutApi.reorderWidget}
          resizeWidget={layoutApi.resizeWidget}
          resetLayout={layoutApi.resetLayout}
          applyPreset={layoutApi.applyPreset}
          saving={layoutApi.saving}
        />
      )}
    </AppShell>
  )
}
