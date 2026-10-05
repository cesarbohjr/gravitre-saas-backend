"use client"

import { useEffect } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreAIWorkspaceHost } from "@/components/gravitre/ai-workspace-host"
import { AiWorkspace } from "@/app/ai/_components/ai-workspace"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"

/** Fixture-only entry to the scoped canonical host; never navigates out of fixture auth. */
export default function AiWorkspaceCapturePage() {
  const { summonWorkspace } = useGravitreAIWorkspace()
  useEffect(() => {
    if (GRAVITRE_AI_FLOAT_ENABLED) summonWorkspace({ presentation: "fullscreen" })
  }, [summonWorkspace])
  return (
    <AppShell title="Gravitre AI">
      <div data-composition="create" data-ai-workspace-capture="" className="flex min-h-0 flex-1 flex-col">
        {GRAVITRE_AI_FLOAT_ENABLED ? <GravitreAIWorkspaceHost fixtureBoundary /> : <AiWorkspace initialMode="auto" />}
      </div>
    </AppShell>
  )
}
