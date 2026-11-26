"use client"

import { useContext, useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { ShotRootAuthReadyContext } from "../shot-auth"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreAIWorkspaceHost } from "@/components/gravitre/ai-workspace-host"
import { AiWorkspace } from "@/app/(app)/ai/_components/ai-workspace"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { isCanonicalPresentationState, type CanonicalPresentationState } from "@/lib/gravitre-ai-presentation"

/** Fixture-only entry to the scoped canonical host; never navigates out of fixture auth. */
export default function AiWorkspaceCapturePage() {
  const rootAuthReady = useContext(ShotRootAuthReadyContext)
  const { summonWorkspace } = useGravitreAIWorkspace()
  const requested = useSearchParams().get("mode") ?? ""
  const presentation: CanonicalPresentationState = isCanonicalPresentationState(requested) ? requested : "fullscreen"
  useEffect(() => {
    // The fixture user resolves before the outer auth gate. Opening during
    // that gap lets the gate close the shared provider as an explicit dismissal.
    if (rootAuthReady && GRAVITRE_AI_FLOAT_ENABLED && presentation !== "minimized") {
      summonWorkspace({ presentation })
    }
  }, [summonWorkspace, presentation, rootAuthReady])
  return (
    <AppShell title="Gravitre AI">
      <div data-composition="create" data-ai-workspace-capture="" className="flex min-h-0 flex-1 flex-col">
        {GRAVITRE_AI_FLOAT_ENABLED ? <GravitreAIWorkspaceHost fixtureBoundary /> : <AiWorkspace initialMode="auto" />}
      </div>
    </AppShell>
  )
}
