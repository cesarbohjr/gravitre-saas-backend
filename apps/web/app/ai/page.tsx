"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { AiWorkspace } from "./_components/ai-workspace"
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
  const initialPrompt = searchParams.get("prompt")?.trim() ?? ""
  const initialConversationId = searchParams.get("c")?.trim() || null

  return (
    <AiWorkspace
      initialMode={initialMode}
      initialPrompt={initialPrompt}
      initialConversationId={initialConversationId}
    />
  )
}

export default function GravitreAiPage() {
  return (
    <AppShell title="Gravitre AI">
      <Suspense fallback={null}>
        <AiPageContent />
      </Suspense>
    </AppShell>
  )
}
