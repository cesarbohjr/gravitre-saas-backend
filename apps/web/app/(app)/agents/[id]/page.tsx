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
import { GravitreEmpty } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Illustration } from "@/components/gravitre/illustration"
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { agentsApi, agentKnowledgeApi } from "@/lib/api"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { AgentIntelligenceVisibilitySection } from "@/components/intelligence/agent-intelligence-visibility-section"
import { AgentDetailHeader, AgentStat } from "@/components/agents/agent-detail-header"
import {
  AgentCapabilitiesEditorCard,
  AgentPersonalityEditorCard,
} from "@/components/gravitre/agent-profile-editors"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import type { Agent as ApiAgent, AgentStatus } from "@/types/api"
import { OPERATIONAL_METHODOLOGY_SHORT } from "@/lib/outcome-labels"
import { responseStyleLabel } from "@/lib/agent-response-style"
import { voiceProfileIsConfigured } from "@/lib/voice-configure-gate"
import { AgentIdentityGovernanceCard } from "@/components/gravitre/agent-identity-governance-card"
import { AgentToolPermissionsPanel } from "@/components/agents/agent-tool-permissions-panel"
import { AgentAutonomyPanel, AgentStrengthProfile } from "@/components/agents/agent-autonomy-panel"
import { useOrgAdmin } from "@/lib/use-org-admin"
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
    { refreshInterval: 30_000 },
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

        <div className="px-[var(--np-page-pad-sm)] pt-5 sm:px-[var(--np-page-pad)]">
          <AgentDetailHeader
            agent={apiAgent}
            chips={
              capabilityProfile?.allowedConnectors ? (
                <span className="inline-flex items-center rounded-full border border-[#e4e4df] px-2.5 py-1 text-[13px] font-medium text-[#55564f] dark:border-[#2a2c29] dark:text-[#a3a49c]">
                  {capabilityProfile.allowedConnectors.length === 0
                    ? "No apps allowed yet"
                    : `${capabilityProfile.allowedConnectors.length} app${capabilityProfile.allowedConnectors.length === 1 ? "" : "s"} allowed`}
                </span>
              ) : null
            }
            actions={
              <>
                <AskGravitreSummonButton className="px-2" />
                <button type="button" className="ag-btn sm ghost" onClick={() => router.push(`/agents/${agent.id}/knowledge`)}>
                  Knowledge
                </button>
                <button type="button" className="ag-btn sm ghost" onClick={() => router.push("/assignments/new?agent=" + agent.id)}>
                  Assign work
                </button>
                <button type="button" className="ag-btn sm dark" onClick={() => router.push(`/agents/${agent.id}/chat`)}>
                  <Icon name="chat" size="sm" />
                  Chat with agent
                </button>
              </>
            }
          >
            <dl className="grid grid-cols-2 divide-[#efefea] lg:grid-cols-4 lg:divide-x dark:divide-[#232522]">
              {apiAgent.stats?.totalRuns != null ? (
                <AgentStat label="Total runs" value={apiAgent.stats.totalRuns.toLocaleString()} hint={apiAgent.stats.totalRuns === 0 ? "No runs yet" : undefined} />
              ) : (
                <AgentStat
                  label="Tasks today"
                  value={agent.stats.tasksCompleted?.toLocaleString() ?? "Not reported"}
                  hint={agent.stats.tasksCompleted === 0 ? "No tasks assigned" : undefined}
                />
              )}
              <AgentStat
                label="Success rate"
                value={agent.stats.successRate != null ? `${Math.round(agent.stats.successRate)}%` : "None yet"}
                hint={agent.stats.successRate != null ? undefined : "Shows once runs finish"}
              />
              <AgentStat
                label="Avg response"
                value={agent.stats.avgResponseTime === "—" ? "None yet" : agent.stats.avgResponseTime}
                hint={agent.stats.avgResponseTime === "—" ? "Shows after the first run" : undefined}
              />
              <AgentStat
                label="Workflows using"
                value={agent.stats.hoursActive?.toLocaleString() ?? "Not reported"}
                hint={agent.stats.hoursActive === 0 ? "Not in any workflow" : undefined}
              />
            </dl>
          </AgentDetailHeader>
        </div>

        <div className="flex-1 px-[var(--np-page-pad-sm)] pb-8 pt-5 sm:px-[var(--np-page-pad)]">
          {error ? <WorkSectionErrorCard title="Could not refresh agent" error={error} onRetry={() => void mutateAgent()} /> : null}
          {capabilityError ? <WorkSectionErrorCard title="Could not refresh access profile" error={capabilityError} onRetry={() => void mutateCapabilities()} /> : null}
          <p className="mb-4 text-xs text-[color:var(--g-text-muted)]">{OPERATIONAL_METHODOLOGY_SHORT}</p>

          <div
            role="tablist"
            aria-label="Agent profile"
            className="mb-6 inline-flex max-w-full gap-0.5 overflow-x-auto rounded-full border border-[#e4e4df] bg-white p-1 [scrollbar-width:none] dark:border-[#2a2c29] dark:bg-[#171917]"
          >
            {[
              { id: "overview", label: "Overview" },
              { id: "personality", label: "Personality" },
              { id: "skills", label: "Capabilities", count: apiAgent.capabilities?.length },
              { id: "governance", label: "Governance" },
              { id: "history", label: "Work history", count: agent.recentWork.length },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={cn(
                  "inline-flex min-h-10 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-4 text-[15px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#19c37d]/50 max-sm:min-h-11",
                  activeTab === tab.id
                    ? "bg-[#0b8a5c] text-white"
                    : "text-[#55564f] hover:bg-[#efefea] hover:text-[#141513] dark:text-[#a3a49c] dark:hover:bg-[#262825] dark:hover:text-[#ededE8]",
                )}
              >
                {tab.label}
                {tab.count != null ? <span className="font-mono text-xs opacity-75">{tab.count}</span> : null}
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
                    connectorProfile={capabilityProfile?.connectorProfile}
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
                <AgentToolPermissionsPanel agentId={agent.id} agentName={agent.name} canEdit={isAdmin} />
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
