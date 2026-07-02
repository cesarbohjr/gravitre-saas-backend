"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { AiWorkspace } from "./_components/ai-workspace"

export default function GravitreAiPage() {
  return (
    <AppShell title="Gravitre AI">
      <AiWorkspace />
    </AppShell>
  )
}
