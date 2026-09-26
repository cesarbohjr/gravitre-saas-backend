"use client"

/**
 * Agent chat route — UX Reset 1.0 Phase 1A.
 *
 * Compatibility: `/agents/[id]/chat` remains. It is not a second live chat runtime.
 * The page sets agent scope and summons the canonical Gravitre AI workspace.
 */

import { use, useEffect } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { agentsApi } from "@/lib/api"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

export default function AgentChatPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id: agentId } = use(params)
  const { user } = useAuth()
  const { data: agent, isLoading: agentLoading } = useSWR(
    user && agentId ? `agent/${agentId}` : null,
    () => agentsApi.get(agentId),
  )
  const { summonWorkspace, setAgentScope, canonicalPresentation, restoreFromHelper } =
    useGravitreAIWorkspace()

  useEffect(() => {
    if (!agent?.id) return
    const scope = {
      agentId: agent.id,
      name: (agent.name || "").trim() || "this agent",
      role: agent.role ?? null,
      responseStyle: agent.responseStyle ?? null,
    }
    setAgentScope(scope)
    summonWorkspace({
      presentation: "fullscreen",
      agentScope: scope,
    })
    return () => {
      setAgentScope(null)
    }
    // Summon once per agent id so compact/minimize on this route is not overwritten.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- agent.id is the scope key
  }, [agent?.id, agent?.name, agent?.role, agent?.responseStyle, setAgentScope, summonWorkspace])

  if (agentLoading && !agent) {
    return (
      <AppShell title="Agent chat">
        <CenteredLoader size="md" label="Loading agent chat" fill="parent" />
      </AppShell>
    )
  }

  if (!agent) {
    return (
      <AppShell title="Agent chat">
        <div className="p-6">
          <p className="text-sm text-[color:var(--g-text-secondary)]">
            Agent not found or you don&apos;t have access.
          </p>
          <Link href="/agents" className="mt-3 inline-block text-sm font-medium text-[color:var(--g-brand)]">
            Back to AI Team
          </Link>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title={agent.name}>
      <div
        className="flex min-h-0 flex-1 flex-col px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]"
        data-gravitre-agent-chat-scope={agent.id}
      >
        <p className="text-xs font-medium text-[color:var(--g-text-tertiary)]">
          Talking to this agent
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[color:var(--g-text-primary)]">
          {agent.name}
        </h1>
        <p className="mt-1 max-w-xl text-sm text-[color:var(--g-text-secondary)]">
          {agent.role ? `${agent.role}. ` : ""}
          Gravitre AI is scoped to this agent — same workspace, not a separate chat product.
        </p>
        {canonicalPresentation === "minimized" ? (
          <div className="mt-4">
            <Button type="button" onClick={() => restoreFromHelper()}>
              Continue talking to {agent.name}
            </Button>
          </div>
        ) : null}
      </div>
    </AppShell>
  )
}
