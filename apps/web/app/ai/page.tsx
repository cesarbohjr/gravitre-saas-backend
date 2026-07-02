"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { AiWorkspace } from "./_components/ai-workspace"
import { LiveActivityRail } from "./_components/live-activity-rail"

export default function GravitreAiPage() {
  return (
    <AppShell title="Gravitre AI">
      <div className="flex h-full">
        <AiWorkspace />
        <LiveActivityRail />
      </div>
    </AppShell>
  )
}
