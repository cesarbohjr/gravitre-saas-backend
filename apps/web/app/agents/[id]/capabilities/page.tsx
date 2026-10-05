"use client"

import Link from "next/link"
import { use } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AgentCapabilitiesCard } from "@/components/gravitre/agent-capabilities-card"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { agentKnowledgeApi } from "@/lib/api"
import { OpenGravitreAIButton } from "@/components/gravitre/open-gravitre-ai-button"
import { Loader2 } from "lucide-react"

export default function AgentCapabilitiesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data: profile, isLoading, error, mutate } = useSWR(
    id ? `agent-capabilities-${id}` : null,
    () => agentKnowledgeApi.getCapabilities(id),
  )

  return (
    <AppShell title="Agent capabilities">
      <div className="mx-auto max-w-4xl space-y-6 px-4 py-6 sm:px-8" data-composition="manage">
        <GravitrePageHeader eyebrow="AI Team · Access" title="Capabilities" description="Reported skills, connector access, and knowledge for this agent." actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="min-h-11" asChild><Link href={`/agents/${id}/knowledge`}>Assigned sources</Link></Button>
            <Button variant="outline" className="min-h-11" asChild><Link href={`/agents/${id}`}>Agent profile</Link></Button>
          </div>
        } />

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" />
            Loading capability profile…
          </div>
        ) : null}

        {error ? <WorkSectionErrorCard title="Could not refresh capabilities" error={error} onRetry={() => void mutate()} /> : null}

        {profile ? (
          <div className="space-y-4">
            <AgentCapabilitiesCard
              capabilities={profile.availableReadActions?.length ? profile.availableReadActions : profile.capabilities}
              permissions={profile.availableWriteActions}
              systems={profile.allowedConnectors}
              memoryCount={profile.memoryCount}
              advisoryOnly={profile.canExecuteWithApproval === false}
            />
          </div>
        ) : null}

        {!isLoading && !error && !profile ? (
          <p className="text-sm text-muted-foreground">
            No capability profile yet. Run the agent on{" "}
            <OpenGravitreAIButton className="text-primary underline-offset-4 hover:underline">
              Gravitre AI
            </OpenGravitreAIButton>{" "}
            to populate learning signals.
          </p>
        ) : null}
      </div>
    </AppShell>
  )
}
