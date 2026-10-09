"use client"

import { useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { InstructionsPage } from "@/components/agents/suite/instructions-page"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"

/**
 * /training is Agents › Instructions. Old deep links to its other tabs go to
 * their new homes: datasets → Intelligence › Data, jobs and fine-tunes → Models.
 */
function TrainingRoute() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const tab = searchParams.get("tab")
  const agentId = searchParams.get("agentId")
  const target =
    tab === "datasets" || (agentId && tab !== "instructions")
      ? `${APP_ROUTES.intelligenceData}${agentId ? `?agentId=${encodeURIComponent(agentId)}` : ""}`
      : tab === "jobs" || tab === "models"
        ? `${APP_ROUTES.models}#training`
        : null
  useEffect(() => {
    if (target) router.replace(target)
  }, [router, target])
  if (target) return null
  return (
    <AppShell title={SURFACE_COPY.trainingInstructions.title}>
      <InstructionsPage />
    </AppShell>
  )
}

export default function TrainingPage() {
  return (
    <Suspense
      fallback={
        <AppShell title={SURFACE_COPY.trainingInstructions.title}>
          <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
            Loading instructions…
          </div>
        </AppShell>
      }
    >
      <TrainingRoute />
    </Suspense>
  )
}
