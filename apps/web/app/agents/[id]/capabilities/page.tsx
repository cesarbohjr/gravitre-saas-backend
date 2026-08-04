"use client"

import Link from "next/link"
import { use } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AgentCapabilitiesCard } from "@/components/gravitre/agent-capabilities-card"
import { Button } from "@/components/ui/button"
import { agentsApi, agentKnowledgeApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { Loader2 } from "lucide-react"

export default function AgentCapabilitiesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data: profile, isLoading, error } = useSWR(
    id ? `agent-capabilities-${id}` : null,
    () => agentKnowledgeApi.getCapabilities(id),
  )
  const { data: agent } = useSWR(id ? `agent-${id}` : null, () => agentsApi.get(id))

  return (
    <AppShell title="Agent capabilities">
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Capabilities</h1>
            <p className="text-sm text-muted-foreground">
              Learned skills, connector access, and knowledge assignments for this agent.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href={`/agents/${id}/knowledge`}>Assigned sources</Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/agents/${id}`}>Agent profile</Link>
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading capability profile…
          </div>
        ) : null}

        {error ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            Capability profile is unavailable for this agent. Try again or check org permissions.
          </p>
        ) : null}

        {profile ? (
          <div className="space-y-4">
            <AgentCapabilitiesCard
              capabilities={profile.availableReadActions?.length ? profile.availableReadActions : profile.capabilities}
              permissions={profile.availableWriteActions}
              systems={profile.allowedConnectors}
              memoryCount={profile.memoryCount}
              advisoryOnly={!profile.canExecuteWithApproval}
            />
          </div>
        ) : null}

        {!isLoading && !error && !profile ? (
          <p className="text-sm text-muted-foreground">
            No capability profile yet. Run the agent on{" "}
            <Link href={APP_ROUTES.gravitreAi} className="text-primary underline-offset-4 hover:underline">
              Gravitre AI
            </Link>{" "}
            to populate learning signals.
          </p>
        ) : null}
      </div>
    </AppShell>
  )
}
