"use client"

import { createElement, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  GlowOrb,
  GridPattern,
  MorphingBackground,
  StatusBeacon,
} from "@/components/gravitre/premium-effects"
import { useAuth } from "@/lib/auth-context"
import { agentsApi, intelligenceApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { useMotionPrefs } from "@/lib/animations"
import { ApiError } from "@/lib/fetcher"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { inferAgentPersonality, resolveAgentRoleIcon } from "@/lib/agent-display"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cn } from "@/lib/utils"
import type { Agent, AgentStatus } from "@/types/api"
import { HealthTab } from "./_components/health-tab"
import { PerformanceTab } from "./_components/performance-tab"
import { LearningTab } from "./_components/learning-tab"
import { OutcomesTab } from "./_components/outcomes-tab"
import { AgentReferenceFoldersPanel } from "@/components/agents/agent-reference-folders-panel"
import { AgentSurfaceSwitch } from "@/components/agents/agent-surface-switch"
import { AgentIntelligenceVisibilitySection } from "@/components/intelligence/agent-intelligence-visibility-section"
import { ArrowLeft, MessageSquare, Sparkles } from "lucide-react"
import { Robot } from "@phosphor-icons/react"

const profileCopy = SURFACE_COPY.pages.agents

type TabKey = "health" | "performance" | "learning" | "outcomes"

function agentInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "AG"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase()
}

function statusLabel(status: AgentStatus): string {
  if (status === "processing") return "Working"
  if (status === "active") return "Active"
  if (status === "error") return "Needs attention"
  return "Idle"
}

function ProfileHeroSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/60 bg-card/70 p-5 backdrop-blur-md sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Skeleton className="h-20 w-20 rounded-2xl sm:h-24 sm:w-24" />
        <div className="min-w-0 flex-1 space-y-3">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-64" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-20 rounded-full" />
            <Skeleton className="h-6 w-24 rounded-full" />
          </div>
        </div>
      </div>
    </div>
  )
}

function ProfileHero({ agent }: { agent: Agent }) {
  const { item } = useMotionPrefs()
  const personality =
    agent.personality?.gradient
      ? agent.personality
      : inferAgentPersonality(agent.department ?? "Operations")
  const beaconStatus =
    agent.status === "processing"
      ? "processing"
      : agent.status === "active"
        ? "active"
        : agent.status === "error"
          ? "error"
          : "idle"

  return (
    <motion.section
      variants={item}
      initial="initial"
      animate="animate"
      className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/75 p-5 shadow-sm backdrop-blur-md sm:p-6"
    >
      <div
        className={cn(
          "pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-gradient-to-br opacity-25 blur-3xl",
          personality.gradient,
        )}
        aria-hidden
      />

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-4 sm:items-center">
          <div className="relative shrink-0">
            <div
              className={cn(
                "flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br text-2xl font-semibold text-white shadow-lg sm:h-24 sm:w-24 sm:text-3xl",
                personality.gradient,
                personality.glow,
              )}
            >
              {agentInitials(agent.name)}
            </div>
            <div className="absolute -bottom-1 -right-1 rounded-full border border-background bg-background p-1">
              <StatusBeacon status={beaconStatus} size="md" pulse={agent.status === "processing"} />
            </div>
          </div>

          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {statusLabel(agent.status)}
            </p>
            <h1 className="mt-1 break-words text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
              {agent.name}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                {createElement(resolveAgentRoleIcon(agent.role, agent.name), {
                  className: "h-3.5 w-3.5 shrink-0",
                  "aria-hidden": true,
                })}
                {agent.role || "Agent"}
              </span>
              {agent.department ? (
                <>
                  <span aria-hidden>·</span>
                  <span>{agent.department}</span>
                </>
              ) : null}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full border border-border/70 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                {agent.stats?.workflowsUsing ?? 0} workflows
              </span>
              {typeof agent.stats?.successRate === "number" ? (
                <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                  {Math.round(agent.stats.successRate)}% success
                </span>
              ) : null}
              {typeof agent.stats?.tasksToday === "number" ? (
                <span className="rounded-full border border-border/70 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                  {agent.stats.tasksToday} tasks today
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 sm:justify-end">
          <Button variant="outline" size="sm" asChild className="gap-2">
            <Link href={APP_ROUTES.intelligenceAgents}>
              <ArrowLeft className="h-4 w-4" aria-hidden />
              All profiles
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild className="gap-2">
            <Link href={`${APP_ROUTES.agents}/${agent.id}`}>
              <Sparkles className="h-4 w-4" aria-hidden />
              AI Team profile
            </Link>
          </Button>
          <Button size="sm" asChild className="gap-2 bg-zinc-900 text-white hover:bg-zinc-800">
            <Link href={`/agents/${agent.id}/chat`}>
              <MessageSquare className="h-4 w-4" aria-hidden />
              Chat
            </Link>
          </Button>
        </div>
      </div>

      {agent.description?.trim() ? (
        <p className="relative mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          {agent.description}
        </p>
      ) : null}
    </motion.section>
  )
}

export default function AgentProfilePage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const { reduced, item } = useMotionPrefs()
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
      <AppShell title={profileCopy.profileTitle}>
        <EmptyState title="Sign in required" description="Log in to view agent profile." />
      </AppShell>
    )
  }

  if (agentError) {
    return (
      <AppShell title={profileCopy.profileTitle}>
        <ErrorState
          title="Unable to load agent"
          description={agentError instanceof ApiError ? agentError.message : "Failed to load agent profile."}
        />
      </AppShell>
    )
  }

  const shellTitle = agent ? `Profile: ${agent.name}` : profileCopy.profileTitle

  return (
    <AppShell title={shellTitle}>
      <div className="relative flex min-h-full flex-col">
        <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
          <MorphingBackground colors={["emerald", "violet", "blue"]} />
          <div className="absolute inset-0 bg-background/88 backdrop-blur-3xl" />
          <GridPattern size={56} color="violet" animated={!reduced} className="opacity-20" />
        </div>
        <div className="pointer-events-none absolute -left-8 top-12 z-0">
          <GlowOrb size={220} color="violet" intensity={0.2} />
        </div>
        <div className="pointer-events-none absolute bottom-8 right-6 z-0">
          <GlowOrb size={180} color="emerald" intensity={0.16} />
        </div>

        <div className="relative z-10 space-y-6 p-4 md:p-6">
          <AgentSurfaceSwitch surface="insights" agentId={id} />
          {agentLoading ? (
            <>
              <ProfileHeroSkeleton />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <Skeleton key={index} className="h-28 rounded-xl" />
                ))}
              </div>
            </>
          ) : !agent ? (
            <EmptyState title="Agent not found" description="This agent does not exist or has been deleted." />
          ) : (
            <>
              <ProfileHero agent={agent} />

              <AgentReferenceFoldersPanel
                folders={agent.referenceFolders ?? []}
                compact={(agent.referenceFolders ?? []).length > 0}
                editHref={`/agents/${agent.id}/knowledge`}
              />

              <AgentIntelligenceVisibilitySection
                agentId={agent.id}
                orgScopedKey={orgId ? `agent-intel-${orgId}-${agent.id}` : null}
              />

              {(() => {
                const agentSuccess = (
                  evaluationsData?.agent_success_rates as Record<string, Record<string, unknown>> | undefined
                )?.[agent.id]
                const hasMeasuredData =
                  agentSuccess?.status === "ok" ||
                  ((outcomesData?.recent_events as Array<Record<string, unknown>> | undefined) ?? []).some(
                    (row) => row.agent_id === agent.id || row.entity_id === agent.id,
                  )
                if (hasMeasuredData) return null
                return (
                  <EmptyState
                    iconSlot={
                      <span className="flex h-16 w-16 items-center justify-center rounded-xl bg-violet-500/10">
                        <Robot
                          className="h-8 w-8 text-violet-600 dark:text-violet-300"
                          weight="duotone"
                          aria-hidden
                        />
                      </span>
                    }
                    title="Agent is ready"
                    description="Performance data appears here as this agent completes tasks. Assign it work to begin building its intelligence profile."
                  />
                )
              })()}

              <Tabs value={tab} onValueChange={(value) => setTab(value as TabKey)}>
                <div className="-mx-1 overflow-x-auto px-1">
                  <TabsList className="inline-flex w-max min-w-full justify-start gap-1 sm:w-full sm:flex-wrap">
                    <TabsTrigger value="health">Health</TabsTrigger>
                    <TabsTrigger value="performance">Performance</TabsTrigger>
                    <TabsTrigger value="learning">Learning</TabsTrigger>
                    <TabsTrigger value="outcomes">Outcomes</TabsTrigger>
                  </TabsList>
                </div>

                <motion.div
                  key={tab}
                  variants={item}
                  initial="initial"
                  animate="animate"
                  className="mt-6"
                >
                  <TabsContent value="health" className="mt-0">
                    <HealthTab agent={agent} enabled={tab === "health"} />
                  </TabsContent>

                  <TabsContent value="performance" className="mt-0">
                    <PerformanceTab
                      agent={agent}
                      evaluationsData={evaluationsData}
                      outcomesData={outcomesData}
                      isLoading={evaluationsLoading || outcomesLoading}
                      enabled={tab === "performance"}
                    />
                  </TabsContent>

                  <TabsContent value="learning" className="mt-0">
                    <LearningTab agent={agent} enabled={tab === "learning"} />
                  </TabsContent>

                  <TabsContent value="outcomes" className="mt-0">
                    <OutcomesTab
                      agent={agent}
                      evaluationsData={evaluationsData}
                      outcomesData={outcomesData}
                      isLoading={evaluationsLoading || outcomesLoading}
                      enabled={tab === "outcomes"}
                    />
                  </TabsContent>
                </motion.div>
              </Tabs>
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
