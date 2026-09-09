"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { AgentKnowledgeShotHarness } from "@/components/agents/knowledge/agent-knowledge-shot-harness"
import { ShotAuthProvider } from "../shot-auth"

export default function AgentKnowledgeShotPage() {
  return (
    <ShotAuthProvider>
      <AppShell title="Agent knowledge">
        <AgentKnowledgeShotHarness />
      </AppShell>
    </ShotAuthProvider>
  )
}
