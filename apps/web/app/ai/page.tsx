"use client"

import { Suspense } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { AiWorkspaceFullPageSlot } from "@/components/gravitre/ai-full-page-slot"
import { AiWorkspace } from "./_components/ai-workspace"
import { useSearchParams } from "next/navigation"
import type { ModeId } from "./_components/ai-mode-config"

function parseInitialMode(value: string | null): ModeId {
  if (value === "auto" || value === "execute" || value === "chat" || value === "find") {
    return value
  }
  return "auto"
}

function AiPageContent() {
  const searchParams = useSearchParams()
  const initialMode = parseInitialMode(searchParams.get("mode"))
  const initialPrompt =
    searchParams.get("prompt")?.trim() || searchParams.get("q")?.trim() || ""
  const initialConversationId =
    searchParams.get("c")?.trim() || searchParams.get("conversation")?.trim() || null
  const initialMessageId = searchParams.get("m")?.trim() || null

  return (
    <AiWorkspace
      initialMode={initialMode}
      initialPrompt={initialPrompt}
      initialConversationId={initialConversationId}
      initialMessageId={initialMessageId}
    />
  )
}

export default function GravitreAiPage() {
  return (
    <AppShell title={SURFACE_COPY.pages.ai.title}>
      <div className="flex min-h-0 flex-1 flex-col">
        {/*
          Phase 5: when the float flag is on, AiWorkspace is root-hosted
          (GravitreAIWorkspaceHost). This page only registers the full-page
          portal slot so the same runtime paints inside AppShell.
        */}
        {GRAVITRE_AI_FLOAT_ENABLED ? (
          <AiWorkspaceFullPageSlot />
        ) : (
          <Suspense fallback={null}>
            <AiPageContent />
          </Suspense>
        )}
      </div>
    </AppShell>
  )
}
