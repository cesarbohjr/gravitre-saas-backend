"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { PageHeader, StatsGrid, StatCard } from "@/components/gravitre/page-header"
import {
  AnimatedCounter,
  GlowOrb,
  GridPattern,
  MorphingBackground,
  StatusBeacon,
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { agentsApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { useMotionPrefs } from "@/lib/animations"
import { ApiError } from "@/lib/fetcher"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { inferAgentPersonality, resolveAgentRoleIcon } from "@/lib/agent-display"
import type { Agent, AgentStatus } from "@/types/api"
import { ArrowRight, Brain, Plus, Search, Sparkles } from "lucide-react"
import { Robot } from "@phosphor-icons/react"

const copy = SURFACE_COPY.hubLinks.agents
const pageCopy = SURFACE_COPY.pages.agents

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

function AgentCardSkeleton() {
  return (
    <div className="rounded-2xl border border-border/60 bg-card/70 p-4 backdrop-blur-sm">
      <div className="flex items-start gap-3">
        <Skeleton className="h-12 w-12 rounded-2xl" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/2" />
          <Skeleton className="h-3 w-24" />
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <Skeleton className="h-6 w-16 rounded-full" />
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>
    </div>
  )
}

function AgentProfileCard({ agent, index }: { agent: Agent; index: number }) {
  const { item } = useMotionPrefs()
  const RoleIcon = resolveAgentRoleIcon(agent.role, agent.name)
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
    <motion.div variants={item} custom={index} className="h-full">
      <Link
        href={`/intelligence/agents/${agent.id}`}
        className={cn(
          "group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border/60 bg-card/75 p-4 shadow-sm backdrop-blur-md transition",
          "hover:-translate-y-0.5 hover:border-emerald-500/30 hover:shadow-lg hover:shadow-emerald-500/10",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/60",
        )}
      >
        <div
          className={cn(
            "pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-gradient-to-br opacity-20 blur-2xl transition group-hover:opacity-40",
            personality.gradient,
          )}
          aria-hidden
        />

        <div className="relative flex items-start gap-3">
          <div className="relative shrink-0">
            <div
              className={cn(
                "flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br text-sm font-semibold text-white shadow-md",
                personality.gradient,
                personality.glow,
              )}
            >
              {agentInitials(agent.name)}
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 rounded-full border border-background bg-background p-0.5">
              <StatusBeacon status={beaconStatus} size="sm" pulse={agent.status === "processing"} />
            </div>
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <h3 className="truncate font-semibold tracking-tight text-foreground">{agent.name}</h3>
              <ArrowRight
                className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100"
                aria-hidden
              />
            </div>
            <p className="mt-0.5 flex items-center gap-1.5 truncate text-sm text-muted-foreground">
              <RoleIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="truncate">{agent.role || "Agent"}</span>
            </p>
            <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {statusLabel(agent.status)}
            </p>
          </div>
        </div>

        <div className="relative mt-4 flex flex-wrap gap-2">
          {agent.department ? (
            <span className="rounded-full border border-border/70 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
              {agent.department}
            </span>
          ) : null}
          <span className="rounded-full border border-border/70 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
            {agent.stats?.workflowsUsing ?? 0} workflows
          </span>
          {typeof agent.stats?.successRate === "number" ? (
            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
              {Math.round(agent.stats.successRate)}% success
            </span>
          ) : null}
        </div>

        <p className="relative mt-3 line-clamp-2 text-sm text-muted-foreground">
          {agent.description?.trim() || pageCopy.profileListHint}
        </p>
      </Link>
    </motion.div>
  )
}

export default function IntelligenceAgentsPage() {
  const { user } = useAuth()
  const router = useRouter()
  const { reduced, container } = useMotionPrefs()
  const [search, setSearch] = useState("")
  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined
  const { data, error, isLoading, mutate } = useSWR(
    user && orgId ? ["intelligence/agents", orgId] : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false },
  )

  const agents = data?.agents ?? []
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return agents
    return agents.filter((agent) => {
      const haystack = `${agent.name} ${agent.role} ${agent.department ?? ""} ${agent.description ?? ""}`.toLowerCase()
      return haystack.includes(q)
    })
  }, [agents, search])

  const activeCount = agents.filter((a) => a.status === "active" || a.status === "processing").length
  const avgSuccess =
    agents.length > 0
      ? Math.round(agents.reduce((sum, agent) => sum + (agent.stats?.successRate ?? 0), 0) / agents.length)
      : 0

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view agent profiles." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load agents."
    return (
      <AppShell title={copy.title}>
        <ErrorState title="Unable to load agents" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className="relative flex min-h-full flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-0 z-0">
          <MorphingBackground colors={["emerald", "violet", "blue"]} />
          <div className="absolute inset-0 bg-background/88 backdrop-blur-3xl" />
          <GridPattern size={56} color="emerald" animated={!reduced} className="opacity-25" />
        </div>
        <div className="pointer-events-none absolute -left-10 top-16 z-0">
          <GlowOrb size={260} color="violet" intensity={0.22} />
        </div>
        <div className="pointer-events-none absolute bottom-10 right-8 z-0">
          <GlowOrb size={200} color="emerald" intensity={0.18} />
        </div>

        <div className="relative z-10 space-y-6 p-4 md:p-6">
          <PageHeader
            title={copy.title}
            description={`${copy.summary} Open a profile for health, performance, learning, and outcomes — or jump to the live constellation.`}
            icon={Brain}
            iconColor="from-emerald-500/20 to-violet-500/20"
            actions={
              <>
                <Button variant="outline" asChild className="gap-2">
                  <Link href={APP_ROUTES.agents}>
                    <Sparkles className="h-4 w-4" aria-hidden />
                    Team constellation
                  </Link>
                </Button>
                <Button asChild className="gap-2 bg-zinc-900 text-white hover:bg-zinc-800">
                  <Link href="/agents/new">
                    <Plus className="h-4 w-4" aria-hidden />
                    New agent
                  </Link>
                </Button>
              </>
            }
          >
            <StatsGrid columns={3}>
              <StatCard
                label="Profiles"
                value={isLoading ? "—" : <AnimatedCounter value={agents.length} duration={0.8} />}
              />
              <StatCard
                label="Active"
                value={isLoading ? "—" : <AnimatedCounter value={activeCount} duration={0.8} />}
                variant="success"
                className={activeCount > 0 ? "border-success/30" : undefined}
              />
              <StatCard
                label="Avg success"
                value={isLoading ? "—" : `${avgSuccess}%`}
                variant="info"
              />
            </StatsGrid>
          </PageHeader>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">{pageCopy.profileListHint}</p>
            <div className="relative w-full sm:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search agents…"
                aria-label="Search agent profiles"
                className="h-9 bg-background/70 pl-9 backdrop-blur-sm"
              />
            </div>
          </div>

          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <AgentCardSkeleton key={index} />
              ))}
            </div>
          ) : agents.length === 0 ? (
            <EmptyState
              title="No agents yet"
              description={pageCopy.profileEmpty}
              iconSlot={<Robot className="h-10 w-10 text-muted-foreground/40" weight="duotone" aria-hidden />}
              action={{ label: "Create an agent", onClick: () => router.push("/agents/new") }}
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              title="No matches"
              description="Try a different name, role, or department."
              iconSlot={<Search className="h-10 w-10 text-muted-foreground/40" aria-hidden />}
            />
          ) : (
            <motion.div
              variants={container}
              initial="initial"
              animate="animate"
              className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
            >
              {filtered.map((agent, index) => (
                <AgentProfileCard key={agent.id} agent={agent} index={index} />
              ))}
            </motion.div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
