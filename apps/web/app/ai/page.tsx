"use client"

import { Suspense, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { AiWorkspaceFullPageSlot } from "@/components/gravitre/ai-full-page-slot"
import { AiWorkspace } from "./_components/ai-workspace"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { writeStoredConversationId } from "@/lib/ai-conversation-storage"
import { APP_ROUTES } from "@/lib/app-routes"
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

function AiCompatibilityRedirect() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { summonWorkspace } = useGravitreAIWorkspace()

  useEffect(() => {
    const conversationId = searchParams.get("c")?.trim() || searchParams.get("conversation")?.trim()
    if (conversationId) writeStoredConversationId(conversationId)
    const prompt = searchParams.get("prompt")?.trim() || searchParams.get("q")?.trim() || ""
    summonWorkspace({
      composerText: prompt || undefined,
    })
    router.replace(APP_ROUTES.home)
  }, [router, searchParams, summonWorkspace])

  return (
    <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-[color:var(--g-text-muted)]">
      Opening Gravitre AI…
    </div>
  )
}

export default function GravitreAiPage() {
  if (GRAVITRE_AI_FLOAT_ENABLED) {
    return (
      <Suspense fallback={null}>
        <AiCompatibilityRedirect />
      </Suspense>
    )
  }

  return (
    <AppShell title={SURFACE_COPY.pages.ai.title}>
      <div className="flex min-h-0 flex-1 flex-col">
        <Suspense fallback={null}>
          <AiPageContent />
        </Suspense>
      </div>
    </AppShell>
  )
}
