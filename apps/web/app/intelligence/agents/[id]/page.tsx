"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth-context"
import { agentsApi, intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { HealthTab } from "./_components/health-tab"
import { PerformanceTab } from "./_components/performance-tab"
import { LearningTab } from "./_components/learning-tab"
import { OutcomesTab } from "./_components/outcomes-tab"
import { AgentReferenceFoldersPanel } from "@/components/agents/agent-reference-folders-panel"
import { AgentIntelligenceVisibilitySection } from "@/components/intelligence/agent-intelligence-visibility-section"
import { Robot } from "@phosphor-icons/react"

type TabKey = "health" | "performance" | "learning" | "outcomes"

export default function AgentProfilePage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [tab, setTab] = useState<TabKey>("health")

  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined

  const { data: agent, error: agentError, isLoading: agentLoading } = useSWR(
    user && id && orgId ? ["agent", orgId, id] : null,
    () => agentsApi.get(id),
    { revalidateOnFocus: false },
  )

  const { data: evaluationsData, isLoading: evaluationsLoading } = useSWR(
    user && id && orgId ? ["intelligence", "evaluations", orgId, 30] : null,
    () => intelligenceApi.intelligenceEvaluations({ periodDays: 30 }),
    { revalidateOnFocus: false },
  )

  const { data: outcomesData, isLoading: outcomesLoading } = useSWR(
    user && id && orgId ? ["intelligence", "outcomes", orgId, 30] : null,
    () => intelligenceApi.outcomes({ periodDays: 30 }),
    { revalidateOnFocus: false },
  )

  if (!user) {
    return (
      <AppShell title="Agent Profile">
        <EmptyState title="Sign in required" description="Log in to view agent profile." />
      </AppShell>
    )
  }

  if (agentError) {
    return (
      <AppShell title="Agent Profile">
        <ErrorState
          title="Unable to load agent"
          description={agentError instanceof ApiError ? agentError.message : "Failed to load agent profile."}
        />
      </AppShell>
    )
  }

  if (agentLoading) {
    return (
      <AppShell title="Agent Profile">
        <div className="p-6 text-sm text-muted-foreground">Loading agent profile…</div>
      </AppShell>
    )
  }

  if (!agent) {
    return (
      <AppShell title="Agent Profile">
        <EmptyState title="Agent not found" description="This agent does not exist or has been deleted." />
      </AppShell>
    )
  }

  const agentSuccess = (evaluationsData?.agent_success_rates as Record<string, Record<string, unknown>> | undefined)?.[
    agent.id
  ]
  const hasMeasuredData =
    agentSuccess?.status === "ok" ||
    ((outcomesData?.recent_events as Array<Record<string, unknown>> | undefined) ?? []).some(
      (row) => row.agent_id === agent.id || row.entity_id === agent.id,
    )

  return (
    <AppShell title={`Profile: ${agent.name}`}>
      <div className="space-y-6 p-4 md:p-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{agent.name}</h1>
          <p className="text-sm text-muted-foreground">
            {agent.role} · {agent.department}
          </p>
        </div>

        <AgentReferenceFoldersPanel
          folders={agent.referenceFolders ?? []}
          compact={(agent.referenceFolders ?? []).length > 0}
          editHref={`/agents/${agent.id}/knowledge`}
        />

        <AgentIntelligenceVisibilitySection
          agentId={agent.id}
          orgScopedKey={orgId ? `agent-intel-${orgId}-${agent.id}` : null}
        />

        {!hasMeasuredData ? (
          <EmptyState
            iconSlot={
              <span className="flex h-16 w-16 items-center justify-center rounded-xl bg-violet-500/10">
                <Robot className="h-8 w-8 text-violet-600 dark:text-violet-300" weight="duotone" aria-hidden />
              </span>
            }
            title="Agent is ready"
            description="Performance data appears here as this agent completes tasks. Assign it work to begin building its intelligence profile."
          />
        ) : null}

        <Tabs value={tab} onValueChange={(value) => setTab(value as TabKey)}>
          <TabsList className="flex w-full flex-wrap justify-start">
            <TabsTrigger value="health">Health</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="learning">Learning</TabsTrigger>
            <TabsTrigger value="outcomes">Outcomes</TabsTrigger>
          </TabsList>

          <TabsContent value="health" className="mt-6">
            <HealthTab agent={agent} enabled={tab === "health"} />
          </TabsContent>

          <TabsContent value="performance" className="mt-6">
            <PerformanceTab
              agent={agent}
              evaluationsData={evaluationsData}
              outcomesData={outcomesData}
              isLoading={evaluationsLoading || outcomesLoading}
              enabled={tab === "performance"}
            />
          </TabsContent>

          <TabsContent value="learning" className="mt-6">
            <LearningTab agent={agent} enabled={tab === "learning"} />
          </TabsContent>

          <TabsContent value="outcomes" className="mt-6">
            <OutcomesTab
              agent={agent}
              evaluationsData={evaluationsData}
              outcomesData={outcomesData}
              isLoading={evaluationsLoading || outcomesLoading}
              enabled={tab === "outcomes"}
            />
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
