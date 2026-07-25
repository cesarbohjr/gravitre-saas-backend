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
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { agentsApi } from "@/lib/api"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { AgentIntelligenceVisibilitySection } from "@/components/intelligence/agent-intelligence-visibility-section"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { AgentIdentityEditor } from "@/components/gravitre/agent-identity-editor"
import { GravitreeLoader } from "@/components/gravitre/gravitree-loader"
import type { Agent as ApiAgent, AgentStatus } from "@/types/api"
import { OPERATIONAL_METHODOLOGY_SHORT } from "@/lib/outcome-labels"

// Types
interface Agent {
  id: string
  name: string
  role: string
  tagline: string
  description: string
  status: "active" | "training" | "limited" | "error"
  trainingProgress: number
  personality: {
    gradient: string
    glow: string
    accent: string
  }
  stats: {
    tasksCompleted: number
    successRate: number
    avgResponseTime: string
    hoursActive: number
    decisionsToday: number
    approvalsNeeded: number
  }
  systems: { name: string; status: "connected" | "warning" | "error"; icon: string }[]
  skills: { name: string; level: number; color: string }[]
  recentWork: { title: string; type: string; time: string; status: "completed" | "pending" | "failed"; confidence: number }[]
}

function mapProfileStatus(status: AgentStatus): Agent["status"] {
  if (status === "processing") return "training"
  if (status === "idle") return "limited"
  if (status === "error") return "error"
  return "active"
}

function toProfileAgent(api: ApiAgent): Agent {
  const gradient = api.personality?.gradient || "from-emerald-500 to-teal-500"
  const glow = api.personality?.glow || "shadow-emerald-500/30"
  return {
    id: api.id,
    name: api.name,
    role: api.role || "Agent",
    tagline: api.department ? `${api.department} specialist` : api.role || "AI teammate",
    description: api.description || "No description yet.",
    status: mapProfileStatus(api.status),
    trainingProgress: Math.min(100, Math.max(0, Math.round(api.stats?.successRate ?? 0))),
    personality: {
      gradient,
      glow,
      accent: api.personality?.color || "emerald",
    },
    stats: {
      tasksCompleted: api.stats?.tasksToday ?? 0,
      successRate: api.stats?.successRate ?? 0,
      avgResponseTime: api.stats?.avgResponseTime || "-",
      hoursActive: api.stats?.workflowsUsing ?? 0,
      decisionsToday: api.stats?.tasksToday ?? 0,
      approvalsNeeded: 0,
    },
    systems: (api.capabilities?.length ? api.capabilities : api.permissions).map((name) => ({
      name,
      status: "connected" as const,
      icon: "database",
    })),
    skills: (api.capabilities || []).map((name) => ({
      name: name.replace(/_/g, " "),
      level: Math.min(100, Math.max(40, api.stats?.successRate ?? 75)),
      color: "emerald",
    })),
    recentWork: api.lastAction
      ? [{
          title: api.lastAction,
          type: "Task",
          time: api.lastActionTime || "Recently",
          status: "completed" as const,
          confidence: Math.round(api.stats?.successRate ?? 0),
        }]
      : [],
  }
}

const statusConfig = {
  active: { label: "Active", color: "text-emerald-400", bgColor: "bg-emerald-500/10", dotColor: "bg-emerald-500" },
  training: { label: "Training", color: "text-blue-400", bgColor: "bg-blue-500/10", dotColor: "bg-blue-500" },
  limited: { label: "Limited", color: "text-amber-400", bgColor: "bg-amber-500/10", dotColor: "bg-amber-500" },
  error: { label: "Error", color: "text-red-400", bgColor: "bg-red-500/10", dotColor: "bg-red-500" },
}

// Animated Avatar — shared identity treatment
function AgentOrb({ agent, apiAgent, status }: { agent: Agent; apiAgent: ApiAgent; status: typeof statusConfig.active }) {
  return (
    <div className="relative">
      <motion.div
        className="absolute inset-0 rounded-full bg-gradient-to-br from-emerald-500/20 to-teal-500/20"
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.5, 0.3, 0.5],
        }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        style={{ filter: "blur(20px)" }}
      />

      <AgentIdentityAvatar agent={apiAgent} size="xl" />

      {agent.status === "active" && (
        <motion.div
          className="absolute -bottom-1 -right-1 flex h-8 w-8 items-center justify-center rounded-full border-2 border-emerald-500 bg-card"
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        >
          <Icon name="activity" size="sm" className="text-emerald-400" />
        </motion.div>
      )}

      <div className="absolute -bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 shadow-lg">
        <motion.div
          className={cn("h-2 w-2 rounded-full", status.dotColor)}
          animate={{ opacity: [1, 0.5, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
        <span className={cn("text-xs font-semibold uppercase tracking-wider", status.color)}>
          {status.label}
        </span>
      </div>
    </div>
  )
}

// Skill Bar with Animation
function SkillBar({ skill, index }: { skill: { name: string; level: number; color: string }; index: number }) {
  const colorClasses: Record<string, string> = {
    emerald: "bg-emerald-500",
    blue: "bg-blue-500",
    violet: "bg-violet-500",
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
      <div className="h-2 rounded-full bg-secondary overflow-hidden">
        <motion.div
          className={cn("h-full rounded-full", colorClasses[skill.color])}
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
      className="group flex items-center gap-4 p-4 rounded-xl border border-border bg-card/50 hover:bg-secondary/50 transition-all cursor-pointer"
    >
      <div className={cn(
        "h-10 w-10 rounded-lg flex items-center justify-center shrink-0",
        work.status === "completed" ? "bg-emerald-500/10" : "bg-amber-500/10"
      )}>
        <Icon 
          name={work.status === "completed" ? "check" : "clock"} 
          size="sm" 
          className={work.status === "completed" ? "text-emerald-400" : "text-amber-400"} 
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
            work.confidence >= 90 ? "text-emerald-400" : "text-amber-400"
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
    connected: "bg-emerald-500",
    warning: "bg-amber-500",
    error: "bg-red-500",
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.1 }}
      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary/50 border border-border"
    >
      <div className="h-6 w-6 rounded-md bg-card flex items-center justify-center">
        <Icon name={system.icon as IconName} size="xs" className="text-muted-foreground" />
      </div>
      <span className="text-sm font-medium text-foreground">{system.name}</span>
      <div className={cn("h-2 w-2 rounded-full ml-auto", statusColors[system.status])} />
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
  const [activeTab, setActiveTab] = useState<"overview" | "skills" | "history">("overview")

  const { data: apiAgent, isLoading, error } = useSWR(
    user && id ? `agent-profile/${id}` : null,
    () => agentsApi.get(id),
    { revalidateOnFocus: false },
  )

  if (isLoading && !apiAgent) {
    return (
      <AppShell title="Agent">
        <div className="flex h-full items-center justify-center">
          <GravitreeLoader size="md" />
        </div>
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
  const status = statusConfig[agent.status]
  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined

  return (
    <AppShell title={agent.name}>
      <div className="flex min-h-full flex-col">
        <div className="border-b border-border px-4 py-3 sm:px-8">
          <AgentSurfaceSwitch surface="operate" agentId={agent.id} />
        </div>
        {/* Hero Header */}
        <div className="relative overflow-hidden border-b border-border">
          {/* Background effects */}
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-teal-500/5" />
          <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
          <div className="absolute bottom-0 left-0 w-96 h-96 bg-gradient-to-tr from-teal-500/10 to-transparent rounded-full blur-3xl translate-y-1/2 -translate-x-1/3" />
          
          <div className="relative px-4 py-5 sm:px-8 sm:py-6">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm mb-5 sm:mb-6">
              <Link
                href="/agents"
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
              >
                <Icon name="chevronLeft" size="sm" />
                AI Team
              </Link>
              <span className="text-muted-foreground/50">/</span>
              <span className="text-foreground">{agent.name}</span>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
              {/* Left: Agent Identity */}
              <div className="lg:col-span-4">
                <div className="flex flex-col items-center text-center">
                  <AgentOrb agent={agent} apiAgent={apiAgent} status={status} />
                  
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="mt-6 w-full"
                  >
                    <h1 className="text-xl sm:text-2xl font-bold text-foreground mb-1 break-words">{agent.name}</h1>
                    <p className="text-muted-foreground mb-2">{agent.role}</p>
                    <p className="text-sm text-emerald-400 font-medium">{agent.tagline}</p>
                    <div className="mt-4 flex justify-center">
                      <AgentIdentityEditor agent={apiAgent} />
                    </div>
                  </motion.div>

                  {/* Action Buttons */}
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="flex flex-col gap-2 mt-5 w-full max-w-xs"
                  >
                    <Button 
                      className="w-full gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0 shadow-lg shadow-emerald-500/25"
                      onClick={() => router.push(`/agents/${agent.id}/chat`)}
                    >
                      <Icon name="chat" size="sm" />
                      Chat with {agent.name}
                    </Button>
                    <div className="grid grid-cols-2 gap-2">
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
                  </motion.div>
                </div>
              </div>

              {/* Right: Stats & Info */}
              <div className="lg:col-span-8">
                {/* Live Stats Grid */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="grid grid-cols-1 gap-4 mb-6 sm:grid-cols-3"
                >
                  {[
                    { label: "Tasks completed (operational)", value: agent.stats.tasksCompleted.toLocaleString(), icon: "check", color: "emerald" },
                    { label: "Success rate (operational)", value: `${agent.stats.successRate}%`, icon: "target", color: "blue" },
                    { label: "Avg Response", value: agent.stats.avgResponseTime, icon: "clock", color: "violet" },
                    { label: "Hours Active", value: agent.stats.hoursActive.toLocaleString(), icon: "activity", color: "amber" },
                    { label: "Decisions Today", value: agent.stats.decisionsToday.toString(), icon: "sparkles", color: "rose" },
                    { label: "Needs Approval", value: agent.stats.approvalsNeeded.toString(), icon: "shield", color: agent.stats.approvalsNeeded > 0 ? "amber" : "emerald" },
                  ].map((stat, i) => (
                    <motion.div
                      key={stat.label}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.3 + i * 0.05 }}
                      className="p-4 rounded-xl border border-border bg-card/50 backdrop-blur-sm"
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "h-10 w-10 rounded-lg flex items-center justify-center",
                          stat.color === "emerald" && "bg-emerald-500/10",
                          stat.color === "blue" && "bg-blue-500/10",
                          stat.color === "violet" && "bg-violet-500/10",
                          stat.color === "amber" && "bg-amber-500/10",
                          stat.color === "rose" && "bg-rose-500/10",
                        )}>
                          <Icon 
                            name={stat.icon as IconName}
                            size="sm" 
                            className={cn(
                              stat.color === "emerald" && "text-emerald-400",
                              stat.color === "blue" && "text-blue-400",
                              stat.color === "violet" && "text-violet-400",
                              stat.color === "amber" && "text-amber-400",
                              stat.color === "rose" && "text-rose-400",
                            )} 
                          />
                        </div>
                        <div>
                          <p className="text-xl font-bold text-foreground">{stat.value}</p>
                          <p className="text-xs text-muted-foreground">{stat.label}</p>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </motion.div>
                <p className="mb-6 text-xs text-muted-foreground">{OPERATIONAL_METHODOLOGY_SHORT}</p>

                {/* Training Progress */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                  className="p-4 rounded-xl border border-border bg-card/50 backdrop-blur-sm"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Icon name="brain" size="sm" className="text-emerald-400" />
                      <span className="text-sm font-medium text-foreground">Training Progress</span>
                    </div>
                    <span className="text-sm font-semibold text-emerald-400">{agent.trainingProgress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-secondary overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${agent.trainingProgress}%` }}
                      transition={{ duration: 1, delay: 0.5 }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Add more business context and examples to improve performance
                  </p>
                </motion.div>
              </div>
            </div>
          </div>
        </div>

        {/* Content Tabs */}
        <div className="flex-1 px-4 py-6 sm:px-8">
          {/* Tab Navigation */}
          <div className="flex items-center gap-1 p-1 rounded-xl bg-secondary/50 w-fit mb-6">
            {[
              { id: "overview", label: "Overview", icon: "info" },
              { id: "skills", label: "Skills", icon: "sparkles" },
              { id: "history", label: "Work History", icon: "history" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  activeTab === tab.id
                    ? "bg-card text-foreground shadow-sm"
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
                <div className="rounded-xl border border-border bg-card/50 p-6 col-span-2">
                  <AgentCapabilitiesCard
                    capabilities={apiAgent.capabilities}
                    permissions={apiAgent.permissions}
                    systems={agent.systems.map((system) => system.name)}
                  />
                </div>

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

                {/* About */}
                <div className="rounded-xl border border-border bg-card/50 p-6">
                  <h3 className="font-semibold text-foreground mb-3">About</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{agent.description}</p>
                </div>

                {/* Connected Systems */}
                <div className="rounded-xl border border-border bg-card/50 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-foreground">Connected Systems</h3>
                    <Button variant="ghost" size="sm" className="gap-1 text-xs">
                      <Icon name="add" size="xs" />
                      Add
                    </Button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {agent.systems.length > 0 ? (
                      agent.systems.map((system, i) => (
                        <SystemBadge key={system.name} system={system} index={i} />
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground col-span-2">No connected systems yet.</p>
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "skills" && (
              <motion.div
                key="skills"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="max-w-2xl"
              >
                <div className="rounded-xl border border-border bg-card/50 p-6">
                  <h3 className="font-semibold text-foreground mb-6">Skill Proficiency</h3>
                  <div className="space-y-5">
                    {agent.skills.length > 0 ? (
                      agent.skills.map((skill, i) => (
                        <SkillBar key={skill.name} skill={skill} index={i} />
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground">No capability profile yet.</p>
                    )}
                  </div>
                </div>
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
                    <p className="text-sm text-muted-foreground">No recent work recorded yet.</p>
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
