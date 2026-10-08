"use client"

import { useState, use } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import useSWR from "swr"
import { AgentCapabilitiesCard } from "@/components/gravitre/agent-capabilities-card"
import { AgentReferenceFoldersPanel } from "@/components/agents/agent-reference-folders-panel"
import { AgentSurfaceSwitch } from "@/components/agents/agent-surface-switch"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitrePageHeader,
} from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Illustration } from "@/components/gravitre/illustration"
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { agentsApi, agentKnowledgeApi } from "@/lib/api"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { AgentIntelligenceVisibilitySection } from "@/components/intelligence/agent-intelligence-visibility-section"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { AgentIdentityEditor } from "@/components/gravitre/agent-identity-editor"
import {
  AgentCapabilitiesEditorCard,
  AgentPersonalityEditorCard,
} from "@/components/gravitre/agent-profile-editors"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import type { Agent as ApiAgent, AgentStatus } from "@/types/api"
import { presentAgentStatus, agentStatusIsLiveWork } from "@/lib/agent-runtime-status"
import { OPERATIONAL_METHODOLOGY_SHORT } from "@/lib/outcome-labels"
import { responseStyleLabel } from "@/lib/agent-response-style"
import { voiceProfileIsConfigured } from "@/lib/voice-configure-gate"
import { AgentIdentityGovernanceCard } from "@/components/gravitre/agent-identity-governance-card"
import { AgentAutonomyPanel, AgentStrengthProfile } from "@/components/agents/agent-autonomy-panel"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useMotionPrefs } from "@/lib/animations"
// Types
interface Agent {
  id: string
  name: string
  role: string
  tagline: string
  description: string
  /** API AgentStatus — never remapped to invented Training/Limited labels. */
  status: AgentStatus
  personality: {
    gradient: string
    glow: string
    accent: string
  }
  stats: {
    tasksCompleted: number | null
    successRate: number | null
    avgResponseTime: string
    hoursActive: number | null
  }
  recentWork: { title: string; type: string; time: string }[]
}

function toProfileAgent(api: ApiAgent): Agent {
  const gradient = api.personality?.gradient || "from-transparent to-transparent"
  const glow = api.personality?.glow || "shadow-none"
  const rawRate = api.stats?.successRate
  const successRate =
    typeof rawRate === "number" && Number.isFinite(rawRate) ? rawRate : null
  return {
    id: api.id,
    name: api.name,
    role: api.role || "Agent",
    tagline: api.department ? `${api.department} specialist` : api.role || "AI teammate",
    description: api.description || "No description yet.",
    status: api.status,
    personality: {
      gradient,
      glow,
      accent: "brand",
    },
    stats: {
      tasksCompleted: api.stats?.tasksToday ?? null,
      successRate,
      avgResponseTime: String(api.stats?.avgResponseTime ?? "—"),
      hoursActive: api.stats?.workflowsUsing ?? null,
    },
    recentWork: api.lastAction
      ? [
          {
            title: api.lastAction,
            type: "Task",
            time: api.lastActionTime || "Not reported",
          },
        ]
      : [],
  }
}

// Avatar — shared identity treatment; pulse only while Running (processing).
function AgentIdentityHero({ agent, apiAgent }: { agent: Agent; apiAgent: ApiAgent }) {
  const { reduced } = useMotionPrefs()
  const status = presentAgentStatus(agent.status)
  const isRunning = agentStatusIsLiveWork(agent.status)

  return (
    <div className="relative">
      <AgentIdentityAvatar agent={apiAgent} size="xl" showStatusDot={false} />

      {isRunning && !reduced ? (
        <motion.div
          className="absolute -bottom-1 -right-1 flex h-8 w-8 items-center justify-center rounded-full border-2 border-divide bg-[color:var(--g-surface-1)]"
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        >
          <Icon name="activity" size="sm" className="text-info" />
        </motion.div>
      ) : null}

      <div
        className={cn(
          "absolute -bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 border border-divide bg-[color:var(--g-surface-1)] px-3 py-1.5 shadow-[var(--np-shadow)]",
          "rounded-[var(--np-radius-md)]",
          status.chipClass,
        )}
      >
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            status.dotColor,
            isRunning && !reduced && "animate-pulse",
          )}
        />
        <span className="text-xs font-medium text-foreground">
          {status.label}
        </span>
      </div>
    </div>
  )
}

function PerformanceFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-[96px]">
      <dt className="text-xs text-[color:var(--g-text-muted)]">{label}</dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums tracking-tight text-foreground">
        {value}
      </dd>
    </div>
  )
}

// Recent Work Item
function WorkItem({ work, index }: { work: Agent["recentWork"][0]; index: number }) {
  const reduced = useReducedMotion()
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="flex items-center gap-3 border-b border-[color:var(--g-border-subtle)] py-3"
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)]">
        <Icon name="history" size="sm" className="text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        <h4 className="line-clamp-1 text-[13px] font-medium text-foreground">{work.title}</h4>
        <p className="text-xs text-muted-foreground">
          {work.type} · {work.time}
        </p>
      </div>
    </motion.div>
  )
}

// System Connection
function SystemBadge({ system, index }: { system: { name: string; icon: string }; index: number }) {
  const reduced = useReducedMotion()
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.1 }}
      className="flex items-center gap-2 rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] px-3 py-2"
    >
      <Icon name={system.icon as IconName} size="xs" className="text-muted-foreground" />
      <span className="truncate text-[13px] font-medium text-foreground">{system.name}</span>
    </motion.div>
  )
}

export default function AgentProfilePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const reduced = useReducedMotion()
  const router = useRouter()
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<
    "overview" | "personality" | "skills" | "governance" | "history"
  >("overview")
  const { isAdmin } = useOrgAdmin()

  const { data: apiAgent, isLoading, error, mutate: mutateAgent } = useSWR(
    user && id ? `agent-profile/${id}` : null,
    () => agentsApi.get(id),
    { revalidateOnFocus: false },
  )

  const { data: capabilityProfile, error: capabilityError, mutate: mutateCapabilities } = useSWR(
    user && id ? `agent/${id}/capabilities` : null,
    () => agentKnowledgeApi.getCapabilities(id),
  )

  usePublishGravitreAISelection(
    apiAgent ? { kind: "agent", id: apiAgent.id, label: apiAgent.name } : null,
  )

  if (isLoading && !apiAgent) {
    return (
      <AppShell title="Agent">
        <CenteredLoader size="md" label="Loading agent" fill="parent" />
      </AppShell>
    )
  }

  if (!apiAgent) {
    return (
      <AppShell title="Agent">
        <div className="flex h-full flex-col items-center justify-center gap-3 text-center px-6">
          <Illustration name={error ? "moment-error" : "moment-focus-time"} width={160} />
          {error ? <WorkSectionErrorCard title="Could not load agent" error={error} onRetry={() => void mutateAgent()} /> : null}
          <p className="text-sm text-muted-foreground">Agent not found or you don&apos;t have access.</p>
          <Button asChild variant="outline" size="sm">
            <Link href="/agents">Back to AI Team</Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  const agent = toProfileAgent(apiAgent)
  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined

  return (
    <AppShell title={agent.name}>
      <div data-composition="manage" className="contents">
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <div className="border-b border-divide px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]">
          <AgentSurfaceSwitch surface="operate" agentId={agent.id} />
        </div>

        <GravitrePageHeader
          title={agent.name}
          description={`${agent.role} · ${agent.tagline}`}
          icon={<NucleoWorkflow className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <AskGravitreSummonButton />
              <Button
                className="min-h-11"
                variant="ghost"
                onClick={() => router.push(`/agents/${agent.id}/knowledge`)}
              >
                <Icon name="database" size="sm" />
                Knowledge
              </Button>
              <Button
                className="min-h-11"
                variant="outline"
                onClick={() => router.push("/assignments/new?agent=" + agent.id)}
              >
                <Icon name="add" size="sm" />
                Assign work
              </Button>
              <Button className="min-h-11" onClick={() => router.push(`/agents/${agent.id}/chat`)}>
                <Icon name="chat" size="sm" />
                Chat
              </Button>
            </div>
          }
        >
          <div className="mb-4 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <AgentIdentityHero agent={agent} apiAgent={apiAgent} />
            <div className="min-w-0 flex-1 space-y-2 text-center sm:pt-2 sm:text-left">
              <p className="text-sm text-[color:var(--g-text-secondary)]">{agent.description}</p>
              <div className="flex justify-center sm:justify-start">
                <AgentIdentityEditor agent={apiAgent} />
              </div>
            </div>
          </div>
        </GravitrePageHeader>

        <div className="flex-1 px-[var(--np-page-pad-sm)] pb-8 pt-2 sm:px-[var(--np-page-pad)]">
          {error ? <WorkSectionErrorCard title="Could not refresh agent" error={error} onRetry={() => void mutateAgent()} /> : null}
          {capabilityError ? <WorkSectionErrorCard title="Could not refresh access profile" error={capabilityError} onRetry={() => void mutateCapabilities()} /> : null}
          <div className="mb-6 border-b border-[color:var(--g-border-subtle)] pb-5">
            <dl className="flex flex-wrap gap-x-8 gap-y-3">
              {apiAgent.stats?.totalRuns != null ? (
                <PerformanceFact label="Total runs" value={apiAgent.stats.totalRuns.toLocaleString()} />
              ) : (
                <PerformanceFact label="Tasks today" value={agent.stats.tasksCompleted?.toLocaleString() ?? "Not reported"} />
              )}
              <PerformanceFact
                label="Success rate"
                value={agent.stats.successRate != null ? `${Math.round(agent.stats.successRate)}%` : "—"}
              />
              <PerformanceFact label="Avg response" value={agent.stats.avgResponseTime} />
              <PerformanceFact
                label="Workflows using"
                value={agent.stats.hoursActive?.toLocaleString() ?? "Not reported"}
              />
            </dl>
            <p className="mt-3 text-xs text-[color:var(--g-text-muted)]">
              {OPERATIONAL_METHODOLOGY_SHORT}
            </p>
          </div>

          <div
            role="tablist"
            aria-label="Agent profile"
            className="mb-6 flex gap-5 overflow-x-auto border-b border-[color:var(--g-border-default)]"
          >
            {[
              { id: "overview", label: "Overview" },
              { id: "personality", label: "Personality" },
              { id: "skills", label: "Capabilities" },
              { id: "governance", label: "Governance" },
              { id: "history", label: "Work history" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={cn(
                  "-mb-px h-11 shrink-0 whitespace-nowrap sm:h-9 border-b-2 px-0.5 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  activeTab === tab.id
                    ? "border-foreground text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <AnimatePresence mode="wait">
            {activeTab === "overview" && (
              <motion.div
                key="overview"
                initial={reduced ? false : { opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, y: -20 }}
                data-agent-overview=""
                className="grid grid-cols-1 gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_360px]"
              >
                <div data-agent-main-field="" className="min-w-0 space-y-6">
                  <div>
                    <AgentAutonomyPanel agentId={agent.id} />
                    <AgentStrengthProfile className="border-t-0" />
                  </div>

                  <AgentCapabilitiesCard
                    capabilities={capabilityProfile?.availableReadActions ?? apiAgent.capabilities}
                    permissions={capabilityProfile?.availableWriteActions}
                    systems={capabilityProfile?.allowedConnectors}
                    memoryCount={capabilityProfile?.memoryCount}
                    advisoryOnly={capabilityProfile?.canExecuteWithApproval === false}
                  />

                  <section aria-labelledby="agent-systems-heading" className="border-t border-[color:var(--g-border-default)] pt-3">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <h3 id="agent-systems-heading" className="text-[13px] font-semibold text-foreground">
                        Allowed connectors
                      </h3>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="min-h-11 gap-1 text-xs"
                        onClick={() => setActiveTab("skills")}
                      >
                        <Icon name="add" size="xs" />
                        Edit
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(capabilityProfile?.allowedConnectors?.length ?? 0) > 0 ? (
                        capabilityProfile?.allowedConnectors?.map((name, i) => (
                          <SystemBadge key={name} system={{ name, icon: "link" }} index={i} />
                        ))
                      ) : (
                        <p className="text-sm text-muted-foreground">Connector access not reported.</p>
                      )}
                    </div>
                  </section>

                  <section aria-labelledby="agent-recent-work-heading" className="border-t border-[color:var(--g-border-default)] pt-3">
                    <div className="flex items-center justify-between gap-3">
                      <h3 id="agent-recent-work-heading" className="text-[13px] font-semibold text-foreground">
                        Recent work
                      </h3>
                      <Button variant="ghost" size="sm" className="min-h-11 text-xs sm:min-h-7" onClick={() => setActiveTab("history")}>
                        Work history
                      </Button>
                    </div>
                    {agent.recentWork.length > 0 ? (
                      agent.recentWork.map((work, i) => <WorkItem key={work.title} work={work} index={i} />)
                    ) : (
                      <p className="mt-1 text-[12px] text-muted-foreground">
                        No recent work recorded yet. Work appears here after this agent completes tasks.
                      </p>
                    )}
                  </section>
                </div>

                <aside data-agent-rail="" aria-label="Knowledge and learning" className="min-w-0 space-y-6">
                  <AgentReferenceFoldersPanel
                    variant="ruled"
                    folders={apiAgent.referenceFolders ?? []}
                    editHref={`/agents/${agent.id}/knowledge`}
                  />
                  <AgentIntelligenceVisibilitySection
                    agentId={agent.id}
                    orgScopedKey={orgId ? `agent-op-${orgId}-${agent.id}` : null}
                    layout="rail"
                  />
                </aside>
              </motion.div>
            )}

            {activeTab === "personality" && (
              <motion.div
                key="personality"
                initial={reduced ? false : { opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, y: -20 }}
                className="max-w-5xl space-y-6"
              >
                <div>
                  <h2 className="text-base font-semibold text-foreground">
                    How {agent.name} works with your team
                  </h2>
                  <p className="mt-1 text-[13px] text-muted-foreground">
                    Currently using{" "}
                    <span className="text-foreground">
                      {voiceProfileIsConfigured(apiAgent.voiceProfile)
                        ? "its own voice"
                        : "the organization's default voice"}
                    </span>{" "}
                    and a{" "}
                    <span className="text-foreground">
                      {responseStyleLabel(apiAgent.responseStyle).toLowerCase()}
                    </span>{" "}
                    response style.
                  </p>
                </div>
                <AgentPersonalityEditorCard
                  agent={apiAgent}
                  onSaved={(next) => void mutateAgent(next, { revalidate: false })}
                />
              </motion.div>
            )}

            {activeTab === "skills" && (
              <motion.div
                key="skills"
                initial={reduced ? false : { opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, y: -20 }}
                className="max-w-3xl space-y-6"
              >
                <AgentCapabilitiesEditorCard
                  agent={apiAgent}
                  onSaved={(next) => void mutateAgent(next, { revalidate: false })}
                />
              </motion.div>
            )}

            {activeTab === "governance" && (
              <motion.div
                key="governance"
                initial={reduced ? false : { opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, y: -20 }}
                className="max-w-3xl space-y-6"
              >
                <AgentAutonomyPanel agentId={agent.id} />
                <AgentIdentityGovernanceCard agentId={agent.id} canEdit={isAdmin} />
              </motion.div>
            )}

            {activeTab === "history" && (
              <motion.div
                key="history"
                initial={reduced ? false : { opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, y: -20 }}
              >
                <div className="space-y-3">
                  {agent.recentWork.length > 0 ? (
                    agent.recentWork.map((work, i) => (
                      <WorkItem key={work.title} work={work} index={i} />
                    ))
                  ) : (
                    <GravitreEmpty
                      illustration="moment-focus-time"
                      title="No recent work recorded yet"
                      hint="Work history appears here after this agent completes tasks."
                    />
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      </div>
    </AppShell>
  )
}
