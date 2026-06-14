"use client"

// Agents Page - AI Team Command Center with Premium Orb System
import { createElement, useState } from "react"
import useSWR, { mutate as globalMutate } from "swr"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatsGrid, StatCard } from "@/components/gravitre/page-header"
import { 
  ParticleField, 
  GlowOrb, 
  MorphingBackground, 
  NeuralNetwork,
  StatusBeacon,
  AnimatedCounter,
  ActivityIndicator
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { 
  Plus, 
  Search,
  RefreshCw,
  Sparkles,
  Brain,
  Zap,
  MessageSquare,
  Activity,
  TrendingUp,
  Megaphone,
  Database,
  PieChart,
  Headphones,
  Bot,
  Play,
  Pause,
  Settings,
  ChevronRight,
  PanelRightClose,
  PanelRightOpen,
  Circle,
  Workflow,
  Shield,
  Blocks,
  BookOpen,
  Users,
  type LucideIcon
} from "lucide-react"
import { cn } from "@/lib/utils"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { agentsApi } from "@/lib/api"
import { inferAgentDepartment, resolveAgentRoleIcon } from "@/lib/agent-display"
import type { Agent as ApiAgent, AgentStatus } from "@/types/api"
import { toast } from "sonner"

type Agent = ApiAgent & {
  model?: string
  knowledgeDocCount?: number
}

const AGENT_DETAIL_PANEL_KEY = "gravitre:agentsDetailPanelOpen"

function deriveModelLabel(input: Record<string, unknown>): string {
  const config = (input.config ?? {}) as Record<string, unknown>
  const activeVersion = (input.active_version ?? input.activeVersion) as Record<string, unknown> | undefined
  const versionConfig = (activeVersion?.config ?? {}) as Record<string, unknown>
  const explicit = String(
    config.model ?? config.model_base ?? versionConfig.model ?? input.model ?? "",
  ).trim()
  if (explicit) return explicit.replace(/^openai\//, "").replace(/^anthropic\//, "Claude ")
  const role = String(input.role ?? "")
  if (role.toLowerCase().includes("data")) return "GPT-5.5"
  if (role.toLowerCase().includes("support")) return "Claude"
  return "GPT-5.5"
}

function deriveKnowledgeDocCount(input: Record<string, unknown>, stats: Record<string, unknown>): number {
  const direct = Number(input.knowledgeDocCount ?? input.knowledge_doc_count ?? NaN)
  if (!Number.isNaN(direct) && direct >= 0) return direct
  const fromStats = Number(stats.knowledgeDocCount ?? stats.knowledge_docs ?? stats.knowledgeDocs ?? NaN)
  if (!Number.isNaN(fromStats) && fromStats >= 0) return fromStats
  return 0
}

function normalizeAgent(input: Record<string, unknown>): Agent {
  const personality = (input.personality ?? {}) as Record<string, unknown>
  const stats = (input.stats ?? {}) as Record<string, unknown>
  const status = String(input.status ?? "idle") as AgentStatus
  const department = String(input.department ?? "Operations")
  return {
    id: String(input.id ?? ""),
    name: String(input.name ?? "Agent"),
    role: String(input.role ?? "Operator"),
    department:
      department === "Marketing" ||
      department === "Sales" ||
      department === "Finance" ||
      department === "Support" ||
      department === "HR"
        ? department
        : "Operations",
    description: String(input.description ?? ""),
    status:
      status === "active" || status === "processing" || status === "error"
        ? status
        : "idle",
    personality: {
      color: String(personality.color ?? "blue"),
      gradient: String(personality.gradient ?? "from-blue-500 to-indigo-500"),
      glow: String(personality.glow ?? "shadow-blue-500/30"),
    },
    stats: {
      tasksToday: Number(stats.tasksToday ?? stats.tasks_today ?? 0),
      successRate: Number(stats.successRate ?? stats.success_rate ?? 0),
      avgResponseTime: String(stats.avgResponseTime ?? stats.avg_response_time ?? "-"),
      workflowsUsing: Number(stats.workflowsUsing ?? stats.workflows_using ?? 0),
    },
    capabilities: Array.isArray(input.capabilities)
      ? (input.capabilities as string[])
      : [],
    permissions: Array.isArray(input.permissions)
      ? (input.permissions as string[])
      : Array.isArray(input.systems)
      ? (input.systems as string[])
      : [],
    lastAction: String(input.lastAction ?? input.last_action ?? "No activity yet"),
    lastActionTime: String(input.lastActionTime ?? input.last_action_time ?? "unknown"),
    model: deriveModelLabel(input),
    knowledgeDocCount: deriveKnowledgeDocCount(input, stats),
  }
}

function normalizeAgentsResponse(payload: unknown): Agent[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw =
    (Array.isArray(model.agents) ? model.agents : null) ??
    (Array.isArray(model.operators) ? model.operators : null) ??
    (Array.isArray(model.data) ? model.data : null)
  if (!raw) return []
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => normalizeAgent(item))
    .filter((item) => item.id.length > 0)
}

const roleIcons: Record<string, LucideIcon> = {
  "Marketing Operator": Megaphone,
  "Sales Assistant": TrendingUp,
  "Data Quality Agent": Database,
  "Finance Reporter": PieChart,
  "Support Coordinator": Headphones,
  "HR Partner": Users,
}

function getAgentIcon(agent: Agent): LucideIcon {
  return resolveAgentRoleIcon(agent.role, agent.name)
}

const statusConfig = {
  active: { label: "Active", color: "text-emerald-400", dotColor: "bg-emerald-500", animate: true },
  idle: { label: "Idle", color: "text-zinc-400", dotColor: "bg-zinc-500", animate: false },
  processing: { label: "Processing", color: "text-blue-400", dotColor: "bg-blue-500", animate: true },
  error: { label: "Error", color: "text-red-400", dotColor: "bg-red-500", animate: false },
}

// Agent Orb Component - Premium visual personality representation with depth
function AgentOrb({ agent, isSelected, onClick, index }: { agent: Agent; isSelected: boolean; onClick: () => void; index: number }) {
  const status = statusConfig[agent.status]
  
  // 3D hover effect
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const rotateX = useTransform(y, [-50, 50], [10, -10])
  const rotateY = useTransform(x, [-50, 50], [-10, 10])

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    x.set(e.clientX - centerX)
    y.set(e.clientY - centerY)
  }

  const handleMouseLeave = () => {
    x.set(0)
    y.set(0)
  }

  return (
    <motion.button
      type="button"
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      layout
      initial={{ opacity: 0, y: 30, scale: 0.8 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.15 } }}
      transition={{ delay: Math.min(index, 8) * 0.05, type: "spring", stiffness: 100 }}
      whileHover={{ scale: 1.04, y: -4 }}
      whileTap={{ scale: 0.97 }}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
      className={cn(
        "relative group flex w-[168px] sm:w-[184px] flex-col items-center rounded-2xl border border-transparent px-3 py-4 text-left transition-colors",
        isSelected ? "border-emerald-500/30 bg-card/70 shadow-lg z-10" : "hover:border-border/60 hover:bg-card/40",
      )}
    >
      <motion.div
        className={cn(
          "pointer-events-none absolute inset-x-4 top-6 h-24 rounded-full blur-2xl transition-opacity duration-500",
          `bg-gradient-to-br ${agent.personality.gradient}`,
        )}
        animate={{ opacity: isSelected ? 0.35 : 0.18 }}
      />

      <div className="relative mb-4 flex h-28 w-28 items-center justify-center">
        {(agent.status === "active" || agent.status === "processing") && (
          <>
            <motion.div
              className={cn(
                "absolute inset-0 rounded-full border-2",
                agent.status === "processing" ? "border-blue-500/40" : "border-emerald-500/30",
              )}
              animate={{ scale: [1, 1.22, 1], opacity: [0.6, 0, 0.6] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut" }}
            />
            <motion.div
              className={cn(
                "absolute inset-0 rounded-full border",
                agent.status === "processing" ? "border-blue-500/20" : "border-emerald-500/20",
              )}
              animate={{ scale: [1, 1.35, 1], opacity: [0.4, 0, 0.4] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut", delay: 0.5 }}
            />
          </>
        )}

        {agent.model ? (
          <span className="absolute -top-1 right-0 z-20 max-w-[88px] truncate rounded-full border border-border bg-card/95 px-2 py-0.5 text-[9px] font-medium text-muted-foreground shadow-sm">
            {agent.model}
          </span>
        ) : null}

        {agent.stats.tasksToday > 0 && (
          <motion.div
            className="absolute -top-1 left-0 z-20 flex h-6 min-w-6 items-center justify-center rounded-full border border-border bg-card px-1 shadow-lg"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: index * 0.1 + 0.3 }}
          >
            <span className="text-[10px] font-bold text-foreground">
              {agent.stats.tasksToday > 99 ? "99+" : agent.stats.tasksToday}
            </span>
          </motion.div>
        )}

        <div
          className={cn(
            "relative flex h-24 w-24 items-center justify-center rounded-full transition-all duration-300",
            `bg-gradient-to-br ${agent.personality.gradient}`,
            isSelected ? "ring-2 ring-white/20 shadow-lg" : "shadow-md",
            agent.status === "error" && "opacity-50 grayscale-[30%]",
          )}
          style={{ transform: "translateZ(20px)" }}
        >
          <div className="absolute inset-2 rounded-full bg-gradient-to-br from-white/20 to-transparent" />
          {createElement(getAgentIcon(agent), {
            className: "relative z-10 h-10 w-10 text-white drop-shadow-lg",
          })}
          {agent.status === "processing" && (
            <motion.div
              className="absolute inset-0 rounded-full border-[3px] border-white/20 border-t-white"
              animate={{ rotate: 360 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
            />
          )}
          {agent.status === "error" && (
            <div className="absolute inset-0 flex items-center justify-center rounded-full bg-red-900/30">
              <Shield className="h-5 w-5 text-red-400" />
            </div>
          )}
        </div>
      </div>

      <div className="relative z-10 w-full space-y-2 text-center">
        <div className="space-y-0.5">
          <p className="truncate text-sm font-semibold text-foreground">{agent.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{agent.role}</p>
        </div>

        <p className="text-[10px] text-muted-foreground">
          <span
            className={cn(
              agent.stats.successRate >= 95
                ? "text-emerald-400"
                : agent.stats.successRate >= 80
                  ? "text-amber-400"
                  : "text-red-400",
            )}
          >
            {agent.stats.successRate}%
          </span>
          <span className="mx-1">·</span>
          <span>{agent.stats.tasksToday} today</span>
        </p>

        {(agent.knowledgeDocCount ?? 0) > 0 ? (
          <a
            href={`/training?agentId=${agent.id}`}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-card/80 px-2 py-0.5 text-[10px] text-muted-foreground hover:border-primary/30 hover:text-foreground"
          >
            <BookOpen className="h-3 w-3" />
            {agent.knowledgeDocCount} docs
          </a>
        ) : (
          <a
            href={`/training?agentId=${agent.id}`}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border bg-card/50 px-2 py-0.5 text-[10px] text-muted-foreground hover:border-primary/30 hover:text-foreground"
          >
            <BookOpen className="h-3 w-3" />
            Add training
          </a>
        )}

        {agent.status === "processing" ? (
          <p className="flex items-center justify-center gap-1 text-[10px] text-blue-400">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
            Running task…
          </p>
        ) : (
          <p className="line-clamp-2 min-h-[2rem] text-[10px] leading-4 text-muted-foreground/80">
            Last ran {agent.lastActionTime}
          </p>
        )}

        <div
          className={cn(
            "mx-auto flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 backdrop-blur-sm",
            agent.status === "error"
              ? "border-red-500/50 bg-red-500/90 text-white"
              : agent.status === "processing"
                ? "border-blue-500/30 bg-blue-500/10"
                : agent.status === "active"
                  ? "border-emerald-500/30 bg-emerald-500/10"
                  : "border-border bg-card/80",
          )}
        >
          <StatusBeacon
            status={
              agent.status === "error"
                ? "error"
                : agent.status === "processing"
                  ? "processing"
                  : agent.status === "active"
                    ? "active"
                    : "idle"
            }
            size="sm"
            pulse={agent.status !== "idle"}
          />
          <span
            className={cn(
              "text-[10px] font-semibold uppercase tracking-wider",
              agent.status === "error" ? "text-white" : status.color,
            )}
          >
            {status.label}
          </span>
        </div>
      </div>
    </motion.button>
  )
}

// Agent Detail Panel
function AgentDetailPanel({
  agent,
  onStart,
  onStop,
  isMutating,
}: {
  agent: Agent
  onStart: (agent: Agent) => Promise<void>
  onStop: (agent: Agent) => Promise<void>
  isMutating: boolean
}) {
  const router = useRouter()
  const status = statusConfig[agent.status]

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="h-full flex flex-col"
    >
      {/* Header */}
      <div className="p-6 border-b border-border">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className={cn(
              "h-14 w-14 rounded-xl flex items-center justify-center",
              `bg-gradient-to-br ${agent.personality.gradient}`
            )}>
              {createElement(getAgentIcon(agent), { className: "h-7 w-7 text-white" })}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold text-foreground">{agent.name}</h2>
                <span className="px-2 py-0.5 rounded-full bg-secondary text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
                  {agent.department}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{agent.role}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {agent.status === "active" ? (
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => void onStop(agent)}
                disabled={isMutating}
              >
                <Pause className="h-3.5 w-3.5" />
                Pause
              </Button>
            ) : agent.status !== "error" ? (
              <Button
                size="sm"
                className="gap-2 bg-zinc-900 hover:bg-zinc-800 text-white"
                onClick={() => void onStart(agent)}
                disabled={isMutating}
              >
                <Play className="h-3.5 w-3.5" />
                Activate
              </Button>
            ) : (
              <Button
                variant="destructive"
                size="sm"
                className="gap-2"
                onClick={() => void onStart(agent)}
                disabled={isMutating}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </Button>
            )}
            <Button 
              variant="ghost" 
              size="icon"
              onClick={() => router.push(`/agents/${agent.id}`)}
            >
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">{agent.description}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className={cn(
            "rounded-md px-2 py-1 text-xs font-medium",
            agent.stats.successRate >= 95 ? "bg-emerald-500/10 text-emerald-400" :
            agent.stats.successRate >= 80 ? "bg-amber-500/10 text-amber-400" : "bg-red-500/10 text-red-400"
          )}>
            {agent.stats.successRate}% success
          </span>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs text-muted-foreground">
            {agent.stats.tasksToday} tasks
          </span>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs text-muted-foreground">
            {agent.stats.avgResponseTime} avg
          </span>
          {agent.model ? (
            <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              {agent.model}
            </span>
          ) : null}
          {(agent.knowledgeDocCount ?? 0) > 0 ? (
            <a
              href={`/training?agentId=${agent.id}`}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <BookOpen className="h-3 w-3" />
              {agent.knowledgeDocCount} docs
            </a>
          ) : (
            <a
              href={`/training?agentId=${agent.id}`}
              className="inline-flex items-center gap-1 rounded-md border border-dashed border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <BookOpen className="h-3 w-3" />
              Add training
            </a>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-border">
        <div className="bg-card p-3 sm:p-4 text-center">
          <div className="text-xl sm:text-2xl font-semibold text-foreground">{agent.stats.tasksToday}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Tasks Today</div>
        </div>
        <div className="bg-card p-4 text-center">
          <div className={cn(
            "text-2xl font-semibold",
            agent.stats.successRate >= 95 ? "text-emerald-400" : 
            agent.stats.successRate >= 80 ? "text-amber-400" : "text-red-400"
          )}>
            {agent.stats.successRate}%
          </div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Success Rate</div>
        </div>
        <div className="bg-card p-4 text-center">
          <div className="text-2xl font-semibold text-foreground">{agent.stats.avgResponseTime}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Avg Response</div>
        </div>
        <div className="bg-card p-4 text-center">
          <div className="text-2xl font-semibold text-foreground">{agent.stats.workflowsUsing}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Workflows</div>
        </div>
      </div>

      {/* Capabilities */}
      <div className="p-6 border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Capabilities
        </h3>
        <div className="flex flex-wrap gap-2">
          {agent.capabilities.map((cap, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05, type: "spring", stiffness: 300, damping: 25 }}
              whileHover={{ scale: 1.05, y: -2 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary border border-border cursor-default hover:border-muted-foreground/50 hover:shadow-sm transition-colors"
            >
              <Sparkles className="h-3 w-3 text-muted-foreground" />
              <span className="text-sm text-foreground">{cap}</span>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Connected Systems */}
      <div className="p-6 border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Connected Systems
        </h3>
        <div className="flex flex-wrap gap-2">
          {agent.permissions.map((perm, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              whileHover={{ scale: 1.05 }}
              className="px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/15 hover:border-blue-500/30 transition-colors cursor-default"
            >
              <span className="text-xs text-blue-400">{perm}</span>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Last Activity */}
      <div className="p-6 flex-1">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Recent Activity
        </h3>
        <div className={cn(
          "rounded-lg border p-4",
          agent.status === "error" ? "border-red-500/30 bg-red-500/5" : "border-border bg-secondary/30"
        )}>
          <div className="flex items-start gap-3">
            <div className={cn(
              "h-8 w-8 rounded-full flex items-center justify-center",
              agent.status === "error" ? "bg-red-500/10" : "bg-blue-500/10"
            )}>
              {agent.status === "processing" ? (
                <Activity className="h-4 w-4 text-blue-400 animate-pulse" />
              ) : agent.status === "error" ? (
                <Shield className="h-4 w-4 text-red-400" />
              ) : (
                <Zap className="h-4 w-4 text-blue-400" />
              )}
            </div>
            <div className="flex-1">
              <p className="text-sm text-foreground">{agent.lastAction}</p>
              <p className="text-xs text-muted-foreground mt-1">{agent.lastActionTime}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Actions - Train Agent, Assign Work, View Memory */}
      <div className="p-6 border-t border-border bg-secondary/30 space-y-3">
        <div className="grid grid-cols-3 gap-2">
          <Button variant="outline" size="sm" className="gap-1.5" asChild>
            <a href={`/agents/${agent.id}?tab=training`}>
              <Brain className="h-3.5 w-3.5" />
              Train
            </a>
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" asChild>
            <a href={`/lite/assign?agent=${agent.id}`}>
              <Play className="h-3.5 w-3.5" />
              Assign
            </a>
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" asChild>
            <a href={`/agents/${agent.id}/memory`}>
              <Database className="h-3.5 w-3.5" />
              Memory
            </a>
          </Button>
        </div>
        <Button variant="outline" className="w-full justify-between" asChild>
          <a href={`/agents/${agent.id}`}>
            View Full Profile
            <ChevronRight className="h-4 w-4" />
          </a>
        </Button>
      </div>
    </motion.div>
  )
}

export default function AgentsPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [isMutatingAgent, setIsMutatingAgent] = useState<string | null>(null)
  const [detailPanelOpen, setDetailPanelOpen] = useState(() => {
    if (typeof window === "undefined") return true
    return window.localStorage.getItem(AGENT_DETAIL_PANEL_KEY) !== "0"
  })

  const toggleDetailPanel = () => {
    setDetailPanelOpen((open) => {
      const next = !open
      window.localStorage.setItem(AGENT_DETAIL_PANEL_KEY, next ? "1" : "0")
      return next
    })
  }
  
  // Fetch agents from API with SWR
  const { data, error, isLoading, mutate } = useSWR<{ agents: Agent[] }>(
    user ? "/api/agents" : null,
    apiFetcher,
    {
      revalidateOnFocus: true,
      revalidateOnMount: true,
      dedupingInterval: 2000,
      onError: (err) => {
        console.error("[v0] Agents fetch error:", err)
      },
    }
  )
  
  const agents = normalizeAgentsResponse(data)
  
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [mesonWizardOpen, setMesonWizardOpen] = useState(false)

  const handleStartAgent = async (agent: Agent) => {
    try {
      setIsMutatingAgent(agent.id)
      await agentsApi.start(agent.id)
      toast.success(`${agent.name} started`)
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to start agent:", err)
      toast.error(`Failed to start ${agent.name}`)
    } finally {
      setIsMutatingAgent((current) => (current === agent.id ? null : current))
    }
  }

  const handleStopAgent = async (agent: Agent) => {
    try {
      setIsMutatingAgent(agent.id)
      await agentsApi.stop(agent.id)
      toast.success(`${agent.name} stopped`)
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to stop agent:", err)
      toast.error(`Failed to stop ${agent.name}`)
    } finally {
      setIsMutatingAgent((current) => (current === agent.id ? null : current))
    }
  }
  
  const selectedAgentOrDefault = selectedAgent ?? agents[0] ?? null
  
  const filteredAgents = agents.filter((a) =>
    a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.role.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const activeCount = agents.filter((a) => a.status === "active" || a.status === "processing").length
  const totalTasks = agents.reduce((sum, a) => sum + a.stats.tasksToday, 0)

  return (
  <AppShell title="Agents">
    <div className="relative flex flex-col lg:flex-row h-full overflow-hidden">
      {/* Premium ambient background */}
      <div className="absolute inset-0 pointer-events-none z-0">
        <MorphingBackground colors={["violet", "blue", "emerald"]} />
        <div className="absolute inset-0 bg-background/85 backdrop-blur-3xl" />
      </div>
      
      {/* Neural network visualization */}
      <div className="absolute inset-0 pointer-events-none z-0 opacity-20">
        <NeuralNetwork nodeCount={25} color="violet" />
      </div>
      
      {/* Floating orbs in background */}
      <div className="absolute top-20 left-20 pointer-events-none z-0">
        <GlowOrb size={300} color="violet" intensity={0.3} />
      </div>
      <div className="absolute bottom-20 right-1/3 pointer-events-none z-0">
        <GlowOrb size={200} color="blue" intensity={0.25} />
      </div>

  {/* Left - Agent Roster with Orbs */}
  <div className="relative z-10 flex-1 flex flex-col lg:border-r border-border/50 backdrop-blur-sm">
          {/* Header */}
          <PageHeader
            title="AI Team"
            description="Your intelligent workforce"
            icon={Brain}
            iconColor="from-violet-500/20 to-purple-500/20"
            actions={
              <>
                <Button 
                  variant="outline" 
                  onClick={() => setMesonWizardOpen(true)} 
                  className="gap-2 border-violet-500/30 hover:bg-violet-500/10 hover:border-violet-500/50"
                >
                  <Blocks className="h-4 w-4 text-violet-400" />
                  <span className="text-violet-400">Build with Meson</span>
                </Button>
                <Button onClick={() => router.push("/agents/new")} className="gap-2 bg-zinc-900 hover:bg-zinc-800 text-white">
                  <Plus className="h-4 w-4" />
                  New Agent
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={toggleDetailPanel}
                  aria-label={detailPanelOpen ? "Hide agent details" : "Show agent details"}
                  className="hidden lg:inline-flex"
                >
                  {detailPanelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
                </Button>
              </>
            }
          >
            <StatsGrid columns={3}>
              <StatCard label="Total" value={agents.length} />
              <StatCard label="Active" value={activeCount} variant="success" />
              <StatCard label="Tasks" value={totalTasks} variant="info" />
            </StatsGrid>
          </PageHeader>

          {/* Search */}
          <div className="p-3 sm:p-4 border-b border-border">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-10 sm:h-9 rounded-lg border border-border bg-secondary pl-9 pr-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          {/* Agent Orb Grid - Premium with particle field */}
          <div className="relative flex-1 p-4 sm:p-8 overflow-auto">
            {/* Particle field behind orbs */}
            <ParticleField count={30} color="violet" interactive className="opacity-40" />
            
            {/* Center stage area */}
            <div className="relative min-h-[400px] flex items-center justify-center">
              {/* Circular platform effect */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <motion.div 
                  className="w-[600px] h-[600px] rounded-full border border-violet-500/10"
                  animate={{ scale: [1, 1.05, 1], opacity: [0.3, 0.5, 0.3] }}
                  transition={{ duration: 8, repeat: Infinity }}
                />
                <motion.div 
                  className="absolute w-[450px] h-[450px] rounded-full border border-blue-500/10"
                  animate={{ scale: [1.05, 1, 1.05], opacity: [0.4, 0.2, 0.4] }}
                  transition={{ duration: 6, repeat: Infinity }}
                />
                <motion.div 
                  className="absolute w-[300px] h-[300px] rounded-full border border-emerald-500/10"
                  animate={{ scale: [1, 1.1, 1], opacity: [0.2, 0.4, 0.2] }}
                  transition={{ duration: 5, repeat: Infinity }}
                />
              </div>
              
              {/* Orb constellation - extra bottom padding for status badges */}
              <div className="relative flex flex-wrap gap-8 sm:gap-10 lg:gap-12 justify-center items-start pt-8 sm:pt-10 pb-28">
                {error ? (
                  <div className="text-center space-y-3 px-4">
                    <p className="text-sm text-destructive">Could not load agents.</p>
                    <Button variant="outline" size="sm" onClick={() => void mutate()}>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Retry
                    </Button>
                  </div>
                ) : isLoading && agents.length === 0 ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Loading agents…
                  </div>
                ) : filteredAgents.length === 0 ? (
                  <div className="text-center space-y-3 px-4">
                    <p className="text-sm text-muted-foreground">
                      {searchQuery ? "No agents match your search." : "No agents yet. Create your first AI teammate."}
                    </p>
                    {!searchQuery ? (
                      <Button onClick={() => router.push("/agents/new")} className="gap-2">
                        <Plus className="h-4 w-4" />
                        New Agent
                      </Button>
                    ) : null}
                  </div>
                ) : (
                  <AnimatePresence mode="popLayout">
                    {filteredAgents.map((agent, index) => (
                      <AgentOrb
                        key={agent.id}
                        agent={agent}
                        index={index}
                        isSelected={selectedAgentOrDefault?.id === agent.id}
                        onClick={() => setSelectedAgent(agent)}
                      />
                    ))}
                  </AnimatePresence>
                )}
              </div>
            </div>
            
            {/* Stats bar - sticky at bottom of scroll container */}
            <motion.div 
              className="sticky bottom-0 left-0 right-0 z-50 flex justify-center py-4 bg-gradient-to-t from-background via-background to-transparent"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
            >
              <div className="flex items-center gap-6 px-6 py-3 rounded-full bg-card border border-border shadow-lg">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                    <Activity className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Active</div>
                    <div className="text-sm font-semibold text-foreground"><AnimatedCounter value={activeCount} duration={1} /></div>
                  </div>
                </div>
                <div className="w-px h-8 bg-border" />
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                    <Zap className="h-4 w-4 text-blue-400" />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Tasks Today</div>
                    <div className="text-sm font-semibold text-foreground"><AnimatedCounter value={totalTasks} duration={1.5} /></div>
                  </div>
                </div>
                <div className="w-px h-8 bg-border" />
                <div className="flex items-center gap-2">
                  <ActivityIndicator value={98} size={36} color="emerald" />
                  <div>
                    <div className="text-xs text-muted-foreground">Health</div>
                    <div className="text-sm font-semibold text-emerald-400">98%</div>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>

{/* Right - Agent Detail Panel - Premium glassmorphism */}
        <AnimatePresence initial={false}>
          {detailPanelOpen ? (
            <motion.div
              key="agent-detail-panel"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 420, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="relative z-10 hidden lg:block overflow-hidden bg-card/40 backdrop-blur-xl border-t lg:border-t-0 lg:border-l border-border/50 shadow-2xl shrink-0"
            >
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-blue-500 to-emerald-500" />
              <AnimatePresence mode="wait">
                {selectedAgentOrDefault && (
                  <AgentDetailPanel
                    key={selectedAgentOrDefault.id}
                    agent={selectedAgentOrDefault}
                    onStart={handleStartAgent}
                    onStop={handleStopAgent}
                    isMutating={isMutatingAgent === selectedAgentOrDefault.id}
                  />
                )}
              </AnimatePresence>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      {/* Meson Wizard */}
      <MesonWizard 
        open={mesonWizardOpen} 
        onClose={() => setMesonWizardOpen(false)}
        onComplete={async (result) => {
          await globalMutate("/api/agents")
          if (result.agentId) {
            router.push(`/agents/${result.agentId}`)
            return
          }
          router.push("/agents")
        }}
      />
    </AppShell>
  )
}
