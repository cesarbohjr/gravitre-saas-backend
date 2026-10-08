"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { HomeDashboard } from "@/components/home/home-dashboard"
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
    if (user) void ensureSelectedOrg().then(setOrgId)
  }, [user])

  const { data: onboarding, error: onboardingError } =
    useSWR<OnboardingProgress>(user ? "/api/onboarding" : null, fetcher, {
      revalidateOnFocus: false,
    })

  const layoutApi = useDashboardLayout(orgId, user?.id ?? null)
  const data = useHomeDashboardData(Boolean(user), layoutApi.layout.globalRange)

  const roleId =
    roleFromOnboardingStepData(onboarding?.step_data) ??
    (WELCOME_ROLES[0]?.id as WelcomeRoleId)
  const roleMeta = WELCOME_ROLES.find((entry) => entry.id === roleId) ?? WELCOME_ROLES[0]

  // Onboarding only decides the getting-started copy, so the dashboard renders
  // (and starts its own fetches) without waiting for it; the getting-started
  // block appears once onboarding has loaded and says it is still needed.
  const showGettingStarted = Boolean(onboarding) && !onboarding?.welcome_completed && !onboarding?.skipped
  const showRoleQuickActions = showGettingStarted || !data.hasLearningSnapshot

  return (
    <AppShell title="Dashboard">
      {onboardingError && !onboarding && user ? (
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
