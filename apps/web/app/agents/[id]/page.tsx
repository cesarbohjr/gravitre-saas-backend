"use client"

import { use, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { fetcher } from "@/lib/fetcher"
import { EmptyState } from "@/components/gravitre/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"

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

interface AgentListResponse {
  agents: Array<{
    id: string
    name: string
    role?: string
    description?: string
    status?: string
    permissions?: string[]
    capabilities?: string[]
  }>
}

interface AgentPerformanceResponse {
  tasksCompleted: number
  avgConfidence: number
  overrideRate: number
  errorRate: number
  weakAreas: string[]
  trendOverTime: Array<{ timestamp: string; success: boolean }>
  meta?: {
    approvalsPending?: number
  }
}

const statusConfig = {
  active: { label: "Active", color: "text-emerald-400", bgColor: "bg-emerald-500/10", dotColor: "bg-emerald-500" },
  training: { label: "Training", color: "text-blue-400", bgColor: "bg-blue-500/10", dotColor: "bg-blue-500" },
  limited: { label: "Limited", color: "text-amber-400", bgColor: "bg-amber-500/10", dotColor: "bg-amber-500" },
  error: { label: "Error", color: "text-red-400", bgColor: "bg-red-500/10", dotColor: "bg-red-500" },
}

// Animated Avatar Orb
function AgentOrb({ agent, status }: { agent: Agent; status: typeof statusConfig.active }) {
  return (
    <div className="relative">
      {/* Outer glow rings */}
      <motion.div
        className="absolute inset-0 rounded-3xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20"
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.5, 0.3, 0.5],
        }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        style={{ filter: "blur(20px)" }}
      />
      
      {/* Main orb */}
      <motion.div
        className={cn(
          "relative h-32 w-32 rounded-3xl flex items-center justify-center bg-gradient-to-br",
          agent.personality.gradient,
          "shadow-2xl"
        )}
        animate={{ 
          boxShadow: agent.status === "active" 
            ? ["0 25px 50px -12px rgba(16, 185, 129, 0.25)", "0 25px 60px -12px rgba(16, 185, 129, 0.4)", "0 25px 50px -12px rgba(16, 185, 129, 0.25)"]
            : "0 25px 50px -12px rgba(16, 185, 129, 0.25)"
        }}
        transition={{ duration: 2, repeat: Infinity }}
      >
        {/* Inner content */}
        <div className="text-center">
          <motion.span 
            className="text-4xl font-bold text-white"
            animate={{ opacity: [0.9, 1, 0.9] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            {agent.name.slice(0, 2).toUpperCase()}
          </motion.span>
        </div>

        {/* Activity indicator */}
        {agent.status === "active" && (
          <motion.div
            className="absolute -bottom-1 -right-1 h-8 w-8 rounded-xl bg-card border-2 border-emerald-500 flex items-center justify-center"
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <Icon name="activity" size="sm" className="text-emerald-400" />
          </motion.div>
        )}
      </motion.div>

      {/* Status badge */}
      <div className={cn(
        "absolute -bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-card shadow-lg",
      )}>
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
        <Icon name={system.icon as any} size="xs" className="text-muted-foreground" />
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
  const [activeTab, setActiveTab] = useState<"overview" | "skills" | "history">("overview")
  const { data: agentList, error: agentError, isLoading: isLoadingAgent } = useSWR<AgentListResponse>(
    "/api/agents",
    fetcher
  )
  const { data: performance, error: performanceError, isLoading: isLoadingPerformance } =
    useSWR<AgentPerformanceResponse>(`/api/agents/${id}/performance`, fetcher)

  useEffect(() => {
    if (agentError || performanceError) {
      toast.error("Failed to load agent performance")
    }
  }, [agentError, performanceError])

  const agent = useMemo<Agent>(() => {
    const source = agentList?.agents?.find((item) => item.id === id)
    const normalizedStatus: Agent["status"] =
      source?.status === "training" || source?.status === "limited" || source?.status === "error"
        ? source.status
        : "active"
    const tasksCompleted = Number(performance?.tasksCompleted ?? 0)
    const avgConfidence = Number(performance?.avgConfidence ?? 0)
    const overrideRate = Number(performance?.overrideRate ?? 0)
    const errors = Number(performance?.errorRate ?? 0)
    const weakAreas = performance?.weakAreas ?? []
    const trend = performance?.trendOverTime ?? []

    return {
      id,
      name: source?.name ?? "Agent",
      role: source?.role ?? "AI Agent",
      tagline: "Performance and reliability profile",
      description: source?.description ?? "No agent description available yet.",
      status: normalizedStatus,
      trainingProgress: Math.max(10, Math.min(100, Math.round(avgConfidence || 40))),
      personality: {
        gradient: "from-emerald-500 to-teal-500",
        glow: "shadow-emerald-500/30",
        accent: "emerald",
      },
      stats: {
        tasksCompleted,
        successRate: Number((100 - errors).toFixed(1)),
        avgResponseTime: "-",
        hoursActive: trend.length * 4,
        decisionsToday: Math.max(0, Math.round(tasksCompleted / 7)),
        approvalsNeeded: Number(performance?.meta?.approvalsPending ?? Math.round(overrideRate / 10)),
      },
      systems: (source?.permissions ?? []).slice(0, 5).map((name) => ({
        name,
        status: "connected",
        icon: "database",
      })),
      skills:
        weakAreas.length > 0
          ? weakAreas.map((name, index) => ({
              name: `Improve ${name}`,
              level: 55 + index * 8,
              color: ["emerald", "blue", "violet", "amber", "rose"][index % 5],
            }))
          : (source?.capabilities ?? []).slice(0, 5).map((name, index) => ({
              name,
              level: 68 + index * 6,
              color: ["emerald", "blue", "violet", "amber", "rose"][index % 5],
            })),
      recentWork: trend.slice(0, 5).reverse().map((entry, index) => ({
        title: `Execution ${index + 1}`,
        type: "Run",
        time: new Date(entry.timestamp).toLocaleString(),
        status: entry.success ? "completed" : "failed",
        confidence: entry.success ? 90 : 45,
      })),
    }
  }, [agentList?.agents, id, performance])

  const status = statusConfig[agent.status]
  const isLoading = isLoadingAgent || isLoadingPerformance

  if (isLoading) {
    return (
      <AppShell title="Agent">
        <div className="p-8 space-y-6">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-40 w-full" />
          <div className="grid grid-cols-3 gap-4">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        </div>
      </AppShell>
    )
  }

  if (agentError || !agentList?.agents?.some((item) => item.id === id)) {
    return (
      <AppShell title="Agent">
        <EmptyState
          variant="error"
          title="Agent not found"
          description="We could not load this agent profile."
          action={{ label: "Back to agents", onClick: () => router.push("/agents") }}
        />
      </AppShell>
    )
  }

  return (
    <AppShell title={agent.name}>
      <div className="flex flex-col min-h-full">
        {/* Hero Header */}
        <div className="relative overflow-hidden border-b border-border">
          {/* Background effects */}
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-teal-500/5" />
          <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
          <div className="absolute bottom-0 left-0 w-96 h-96 bg-gradient-to-tr from-teal-500/10 to-transparent rounded-full blur-3xl translate-y-1/2 -translate-x-1/3" />
          
          <div className="relative px-8 py-8">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm mb-8">
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

            <div className="grid grid-cols-12 gap-8">
              {/* Left: Agent Identity */}
              <div className="col-span-4">
                <div className="flex flex-col items-center text-center">
                  <AgentOrb agent={agent} status={status} />
                  
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="mt-8"
                  >
                    <h1 className="text-3xl font-bold text-foreground mb-1">{agent.name}</h1>
                    <p className="text-muted-foreground mb-2">{agent.role}</p>
                    <p className="text-sm text-emerald-400 font-medium">{agent.tagline}</p>
                  </motion.div>

                  {/* Action Buttons */}
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="flex flex-col gap-2 mt-6 w-full max-w-xs"
                  >
                    <Button 
                      className="w-full gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0 shadow-lg shadow-emerald-500/25"
                      onClick={() => router.push("/assignments/new?agent=" + agent.id)}
                    >
                      <Icon name="add" size="sm" />
                      Assign Work
                    </Button>
                    <div className="grid grid-cols-2 gap-2">
                      <Button 
                        variant="outline" 
                        className="gap-2"
                        onClick={() => router.push("/training?agent=" + agent.id)}
                      >
                        <Icon name="brain" size="sm" />
                        Train
                      </Button>
                      <Button 
                        variant="outline" 
                        className="gap-2"
                        onClick={() => router.push(`/agents/${agent.id}/memory`)}
                      >
                        <Icon name="database" size="sm" />
                        Memory
                      </Button>
                    </div>
                  </motion.div>
                </div>
              </div>

              {/* Right: Stats & Info */}
              <div className="col-span-8">
                {/* Live Stats Grid */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="grid grid-cols-3 gap-4 mb-6"
                >
                  {[
                    { label: "Tasks Completed", value: agent.stats.tasksCompleted.toLocaleString(), icon: "check", color: "emerald" },
                    { label: "Success Rate", value: `${agent.stats.successRate}%`, icon: "target", color: "blue" },
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
                            name={stat.icon as any} 
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
        <div className="flex-1 px-8 py-6">
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
                <Icon name={tab.icon as any} size="sm" />
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
                className="grid grid-cols-2 gap-6"
              >
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
                    {agent.systems.map((system, i) => (
                      <SystemBadge key={system.name} system={system} index={i} />
                    ))}
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
                    {agent.skills.map((skill, i) => (
                      <SkillBar key={skill.name} skill={skill} index={i} />
                    ))}
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
                  {agent.recentWork.map((work, i) => (
                    <WorkItem key={work.title} work={work} index={i} />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </AppShell>
  )
}
