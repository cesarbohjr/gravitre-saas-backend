"use client"

import { useState, use } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { AgentCapabilitiesCard } from "@/components/gravitre/agent-capabilities-card"
import { AgentReferenceFoldersPanel } from "@/components/agents/agent-reference-folders-panel"
import { AgentSurfaceSwitch } from "@/components/agents/agent-surface-switch"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { agentsApi } from "@/lib/api"
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
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useMotionPrefs } from "@/lib/animations"
import { TYPE } from "@/lib/design-system"

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
    tasksCompleted: number
    successRate: number | null
    avgResponseTime: string
    hoursActive: number
    decisionsToday: number
    approvalsNeeded: number
  }
  systems: { name: string; status: "connected" | "warning" | "error"; icon: string }[]
  skills: { name: string; level: number; color: string }[]
  recentWork: { title: string; type: string; time: string; status: "completed" | "pending" | "failed"; confidence: number }[]
}

function toProfileAgent(api: ApiAgent): Agent {
  const gradient = api.personality?.gradient || "from-[color:var(--g-brand)] to-[color:var(--g-brand-active)]"
  const glow = api.personality?.glow || "shadow-[color:var(--g-brand)]/20"
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
      tasksCompleted: api.stats?.tasksToday ?? 0,
      successRate,
      avgResponseTime: String(api.stats?.avgResponseTime ?? "—"),
      hoursActive: api.stats?.workflowsUsing ?? 0,
      decisionsToday: api.stats?.tasksToday ?? 0,
      approvalsNeeded: 0,
    },
    systems: (api.permissions ?? []).slice(0, 6).map((name) => ({
      name,
      status: "connected" as const,
      icon: "link",
    })),
    skills: (api.capabilities || []).map((name) => ({
      name: name.replace(/_/g, " "),
      // Only show a numeric level when successRate exists — never invent a floor.
      level: successRate != null ? Math.min(100, Math.max(0, Math.round(successRate))) : 0,
      color: "brand",
    })),
    recentWork: api.lastAction
      ? [
          {
            title: api.lastAction,
            type: "Task",
            time: api.lastActionTime || "Recently",
            status: "completed" as const,
            confidence: successRate != null ? Math.round(successRate) : 0,
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
      <AgentIdentityAvatar agent={apiAgent} size="xl" showStatusDot />

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
        <span className={cn("text-xs font-semibold uppercase tracking-[0.14em]", status.color)}>
          {status.label}
        </span>
      </div>
    </div>
  )
}

// Skill Bar with Animation
function SkillBar({ skill, index }: { skill: { name: string; level: number; color: string }; index: number }) {
  const colorClasses: Record<string, string> = {
    brand: "bg-[color:var(--g-brand)]",
    emerald: "bg-[color:var(--g-brand)]",
    blue: "bg-blue-500",
    signal: "bg-[color:var(--g-signal)]",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="group"
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm font-medium text-foreground">{skill.name}</span>
        <span className="text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
          {skill.level}%
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[color:var(--g-surface-2)]">
        <motion.div
          className={cn("h-full rounded-full", colorClasses[skill.color] ?? colorClasses.brand)}
          initial={{ width: 0 }}
          animate={{ width: `${skill.level}%` }}
          transition={{ duration: 1, delay: 0.2 + index * 0.1, ease: "easeOut" }}
        />
      </div>
    </motion.div>
  )
}

// Recent Work Item
function WorkItem({ work, index }: { work: Agent["recentWork"][0]; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="group flex cursor-pointer items-center gap-4 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)] transition-colors hover:bg-[color:var(--g-surface-2)]"
    >
      <div className={cn(
        "flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--np-radius-md)]",
        work.status === "completed" ? "bg-[color:var(--g-brand-soft)]" : "bg-warning/10"
      )}>
        <Icon 
          name={work.status === "completed" ? "check" : "clock"} 
          size="sm" 
          className={work.status === "completed" ? "text-[color:var(--g-brand)]" : "text-warning"} 
        />
      </div>
      
      <div className="flex-1 min-w-0">
        <h4 className="font-medium text-foreground line-clamp-1">{work.title}</h4>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{work.type}</span>
          <span className="text-muted-foreground/50">|</span>
          <span>{work.time}</span>
        </div>
      </div>

      {work.confidence > 0 && (
        <div className="text-right shrink-0">
          <span className={cn(
            "text-sm font-semibold",
            work.confidence >= 90 ? "text-[color:var(--g-brand)]" : "text-warning"
          )}>
            {work.confidence}%
          </span>
          <p className="text-[10px] text-muted-foreground">confidence</p>
        </div>
      )}

      <Icon name="chevronRight" size="sm" className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
    </motion.div>
  )
}

// System Connection
function SystemBadge({ system, index }: { system: Agent["systems"][0]; index: number }) {
  const statusColors = {
    connected: "bg-[color:var(--status-verified)]",
    warning: "bg-[color:var(--status-pending)]",
    error: "bg-[color:var(--status-failed)]",
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.1 }}
      className="flex items-center gap-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-3 py-2"
    >
      <div className="flex h-6 w-6 items-center justify-center rounded-[var(--np-radius-sm)] bg-[color:var(--g-surface-1)]">
        <Icon name={system.icon as IconName} size="xs" className="text-muted-foreground" />
      </div>
      <span className="text-sm font-medium text-foreground">{system.name}</span>
      <div className={cn("ml-auto h-2 w-2 rounded-full", statusColors[system.status])} />
    </motion.div>
  )
}

export default function AgentProfilePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
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

  if (isLoading && !apiAgent) {
    return (
      <AppShell title="Agent">
        <CenteredLoader size="md" label="Loading agent" fill="parent" />
      </AppShell>
    )
  }

  if (!apiAgent || error) {
    return (
      <AppShell title="Agent">
        <div className="flex h-full flex-col items-center justify-center gap-3 text-center px-6">
          <p className="text-sm text-muted-foreground">Agent not found or you don&apos;t have access.</p>
          <Link href="/agents">
            <Button variant="outline" size="sm">Back to AI Team</Button>
          </Link>
        </div>
      </AppShell>
    )
  }

  const agent = toProfileAgent(apiAgent)
  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined

  return (
    <AppShell title={agent.name}>
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <div className="border-b border-divide px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]">
          <AgentSurfaceSwitch surface="operate" agentId={agent.id} />
        </div>

        <GravitrePageHeader
          eyebrow="AI Team"
          title={agent.name}
          description={`${agent.role} · ${agent.tagline}`}
          icon={<NucleoAgent className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                className="gap-2"
                onClick={() => router.push(`/agents/${agent.id}/chat`)}
              >
                <Icon name="chat" size="sm" />
                Chat with {agent.name}
              </Button>
              <Button
                variant="outline"
                className="gap-2"
                onClick={() => router.push(`/agents/${agent.id}/knowledge`)}
              >
                <Icon name="database" size="sm" />
                Knowledge
              </Button>
              <Button
                variant="outline"
                className="gap-2"
                onClick={() => router.push("/assignments/new?agent=" + agent.id)}
              >
                <Icon name="add" size="sm" />
                Assign
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

        <div className="flex-1 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          <section className="mb-6 grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-3">
            <GravitreMetric
              label="Tasks completed (operational)"
              value={agent.stats.tasksCompleted.toLocaleString()}
            />
            <GravitreMetric
              label="Success rate (operational)"
              value={agent.stats.successRate != null ? `${Math.round(agent.stats.successRate)}%` : "—"}
            />
            <GravitreMetric label="Avg Response" value={agent.stats.avgResponseTime} />
            <GravitreMetric
              label="Workflows using"
              value={agent.stats.hoursActive > 0 ? agent.stats.hoursActive.toLocaleString() : "—"}
            />
            <GravitreMetric label="Decisions Today" value={agent.stats.decisionsToday.toString()} />
            <GravitreMetric
              label="Needs Approval"
              value={agent.stats.approvalsNeeded.toString()}
            />
          </section>
          <p className="mb-6 text-xs text-[color:var(--g-text-muted)]">{OPERATIONAL_METHODOLOGY_SHORT}</p>

          {/* Tab Navigation */}
          <div className="mb-6 flex w-fit flex-wrap items-center gap-1 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)] p-1">
            {[
              { id: "overview", label: "Overview", icon: "info" },
              { id: "personality", label: "Personality", icon: "sparkles" },
              { id: "skills", label: "Capabilities", icon: "settings" },
              { id: "governance", label: "Governance", icon: "shield" },
              { id: "history", label: "Work History", icon: "history" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={cn(
                  "flex items-center gap-2 rounded-[var(--np-radius-md)] px-4 py-2 text-sm font-medium transition-all",
                  activeTab === tab.id
                    ? "bg-[color:var(--g-surface-1)] text-foreground shadow-[var(--np-shadow)]"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon name={tab.icon as IconName} size="sm" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <AnimatePresence mode="wait">
            {activeTab === "overview" && (
              <motion.div
                key="overview"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="grid grid-cols-1 gap-6 sm:grid-cols-2"
              >
                <GravitreSurface className="col-span-2">
                  <AgentCapabilitiesCard
                    capabilities={apiAgent.capabilities}
                    permissions={apiAgent.permissions}
                    systems={agent.systems.map((system) => system.name)}
                  />
                </GravitreSurface>

                <div className="col-span-2">
                  <AgentReferenceFoldersPanel
                    folders={apiAgent.referenceFolders ?? []}
                    editHref={`/agents/${agent.id}/knowledge`}
                  />
                </div>

                <div className="col-span-2">
                  <AgentIntelligenceVisibilitySection
                    agentId={agent.id}
                    orgScopedKey={orgId ? `agent-op-${orgId}-${agent.id}` : null}
                    compact
                  />
                </div>

                <GravitreSurface>
                  <h3 className="mb-3 font-semibold text-foreground">About</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">{agent.description}</p>
                </GravitreSurface>

                <GravitreSurface>
                  <div className="mb-4 flex items-center justify-between">
                    <h3 className="font-semibold text-foreground">Connected Systems</h3>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="gap-1 text-xs"
                      onClick={() => setActiveTab("skills")}
                    >
                      <Icon name="add" size="xs" />
                      Edit
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {agent.systems.length > 0 ? (
                      agent.systems.map((system, i) => (
                        <SystemBadge key={system.name} system={system} index={i} />
                      ))
                    ) : (
                      <p className="col-span-2 text-sm text-muted-foreground">No connected systems yet.</p>
                    )}
                  </div>
                </GravitreSurface>

                <GravitreSurface className="col-span-2" padded={false}>
                  <div className="p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Icon name="brain" size="sm" className="text-[color:var(--g-brand)]" />
                        <span className={TYPE.cardTitle}>Success rate</span>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-foreground">
                        {agent.stats.successRate != null ? `${Math.round(agent.stats.successRate)}%` : "—"}
                      </span>
                    </div>
                    <p className={TYPE.meta}>
                      {agent.stats.successRate != null
                        ? "From agent stats when tasks exist — not a training completion badge."
                        : "No success rate yet. Completes after the agent has task outcomes."}
                    </p>
                  </div>
                </GravitreSurface>
              </motion.div>
            )}

            {activeTab === "personality" && (
              <motion.div
                key="personality"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="max-w-3xl space-y-4"
              >
                <GravitreSurface padded={false} className="bg-[color:var(--g-surface-2)] px-4 py-3 text-sm text-muted-foreground">
                  Current: spoken voice{" "}
                  {voiceProfileIsConfigured(apiAgent.voiceProfile)
                    ? "configured"
                    : "org default"}
                  {" · "}
                  response style {responseStyleLabel(apiAgent.responseStyle)}
                </GravitreSurface>
                <AgentPersonalityEditorCard
                  agent={apiAgent}
                  onSaved={(next) => void mutateAgent(next, { revalidate: false })}
                />
              </motion.div>
            )}

            {activeTab === "skills" && (
              <motion.div
                key="skills"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="max-w-3xl space-y-6"
              >
                <AgentCapabilitiesEditorCard
                  agent={apiAgent}
                  onSaved={(next) => void mutateAgent(next, { revalidate: false })}
                />
                {agent.skills.length > 0 ? (
                  <GravitreSurface>
                    <h3 className="mb-6 font-semibold text-foreground">Skill overview</h3>
                    <div className="space-y-5">
                      {agent.skills.map((skill, i) => (
                        <SkillBar key={skill.name} skill={skill} index={i} />
                      ))}
                    </div>
                  </GravitreSurface>
                ) : null}
              </motion.div>
            )}

            {activeTab === "governance" && (
              <motion.div
                key="governance"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="max-w-3xl"
              >
                <AgentIdentityGovernanceCard agentId={agent.id} canEdit={isAdmin} />
              </motion.div>
            )}

            {activeTab === "history" && (
              <motion.div
                key="history"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
              >
                <div className="space-y-3">
                  {agent.recentWork.length > 0 ? (
                    agent.recentWork.map((work, i) => (
                      <WorkItem key={work.title} work={work} index={i} />
                    ))
                  ) : (
                    <GravitreEmpty
                      icon={<Icon name="history" size="sm" />}
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
    </AppShell>
  )
}
