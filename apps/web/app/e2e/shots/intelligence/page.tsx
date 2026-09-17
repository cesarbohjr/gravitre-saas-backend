"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { IntelligenceHubTabs } from "@/components/intelligence/intelligence-hub-tabs"
import { ShotAuthProvider } from "../shot-auth"

/** I11 hub contract without /api/intelligence/page-context or a live login. */
export default function IntelligenceHubShotPage() {
  return (
    <ShotAuthProvider>
      <AppShell title="Intelligence">
        <div className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
          <IntelligenceHubTabs active="overview" />
        </div>
      </AppShell>
    </ShotAuthProvider>
  )
}
