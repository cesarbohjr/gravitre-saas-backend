"use client"

// Agents Page - AI Team Command Center with Premium Orb System
import { createElement, Suspense, useEffect, useMemo, useRef, useState } from "react"
import useSWR, { mutate as globalMutate } from "swr"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatsGrid, StatCard } from "@/components/gravitre/page-header"
import { 
  ParticleField, 
  GlowOrb, 
  MorphingBackground, 
  NeuralNetwork,
  StatusBeacon,
  AnimatedCounter
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useMotionPrefs } from "@/lib/animations"
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
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
  X,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  PanelRightClose,
  PanelRightOpen,
  Circle,
  Workflow,
  Shield,
  BookOpen,
  Users,
  type LucideIcon
} from "lucide-react"
import { cn } from "@/lib/utils"
import { AgentSurfaceSwitch } from "@/components/agents/agent-surface-switch"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { agentsApi } from "@/lib/api"
import { inferAgentDepartment, resolveAgentRoleIcon } from "@/lib/agent-display"
import { resolveAgentIdentity } from "@/lib/agent-identity"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { departmentGradient } from "@/lib/department-gradient"
import type { Agent as ApiAgent, AgentStatus } from "@/types/api"
import { toast } from "sonner"
import { formatDistanceToNow } from "date-fns"

type AgentRecentTask = {
  id: string
  title: string
  time: string
  status: string
}

type Agent = ApiAgent & {
  model?: string
  knowledgeDocCount?: number
  recentTasks?: AgentRecentTask[]
  config?: Record<string, unknown>
}

const AGENT_DETAIL_PANEL_KEY = "gravitre:agentsDetailPanelOpen"
const AGENT_HEADER_COLLAPSED_KEY = "gravitre:agentsHeaderCollapsed"
const AGENTS_REFRESH_MS = 30_000

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
    icon: typeof input.icon === "string" ? input.icon : null,
    avatarColor:
      typeof input.avatarColor === "string"
        ? input.avatarColor
        : typeof input.avatar_color === "string"
          ? input.avatar_color
          : null,
    avatarUrl:
      typeof input.avatarUrl === "string"
        ? input.avatarUrl
        : typeof input.avatar_url === "string"
          ? input.avatar_url
          : null,
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
    recentTasks: Array.isArray(input.recentTasks)
      ? (input.recentTasks as AgentRecentTask[])
      : Array.isArray(input.recent_tasks)
        ? (input.recent_tasks as AgentRecentTask[])
        : [],
    config:
      input.config && typeof input.config === "object"
        ? (input.config as Record<string, unknown>)
        : undefined,
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
  active: { label: "Active", color: "text-success", dotColor: "bg-success", animate: true },
  idle: { label: "Idle", color: "text-muted-foreground", dotColor: "bg-muted-foreground", animate: false },
  processing: { label: "Processing", color: "text-info", dotColor: "bg-info", animate: true },
  error: { label: "Error", color: "text-destructive", dotColor: "bg-destructive", animate: false },
}

function shouldShowSuccessRate(agent: Agent): boolean {
  return !(agent.status === "idle" && agent.stats.successRate === 0)
}

function successRateColorClass(rate: number): string {
  if (rate >= 90) return "text-success"
  if (rate >= 70) return "text-warning"
  return "text-destructive"
}

function successRateBadgeClass(rate: number): string {
  if (rate >= 90) return "bg-success/10 text-success"
  if (rate >= 70) return "bg-warning/10 text-warning"
  return "bg-destructive/10 text-destructive"
}

function formatModelDisplayName(model: string, maxLength = 15): string {
  const trimmed = model.trim()
  if (trimmed.length <= maxLength) return trimmed
  return `${trimmed.slice(0, maxLength - 1)}…`
}

function AgentModelBadge({
  model,
  className,
  variant = "orb",
}: {
  model: string
  className?: string
  variant?: "orb" | "panel"
}) {
  const display = formatModelDisplayName(model, variant === "orb" ? 14 : 22)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={className}
          onClick={(event) => event.stopPropagation()}
          onPointerDown={(event) => event.stopPropagation()}
        >
          {display}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs font-mono text-xs">
        {model}
      </TooltipContent>
    </Tooltip>
  )
}

function agentMatchesQuery(agent: Agent, query: string): boolean {
  const haystack = [
    agent.name,
    agent.role,
    agent.department,
    agent.description,
    agent.model ?? "",
    statusConfig[agent.status].label,
    ...agent.capabilities,
    ...agent.permissions,
  ]
    .join(" ")
    .toLowerCase()
  return haystack.includes(query)
}

function formatTaskTime(value: string): string {
  if (!value || value === "unknown" || value === "recently") return value
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return formatDistanceToNow(date, { addSuffix: true })
}

function getAgentRecentTasks(agent: Agent): AgentRecentTask[] {
  if (agent.recentTasks && agent.recentTasks.length > 0) {
    return agent.recentTasks.slice(0, 3)
  }
  if (
    agent.lastAction &&
    agent.lastAction !== "No recent activity" &&
    agent.lastAction !== "No activity yet"
  ) {
    return [
      {
        id: `${agent.id}-last`,
        title: agent.lastAction,
        time: agent.lastActionTime,
        status: agent.status === "processing" ? "running" : agent.status,
      },
    ]
  }
  return []
}

function taskStatusBadgeClass(status: string): string {
  switch (status) {
    case "completed":
      return "bg-success/10 text-success"
    case "running":
    case "processing":
      return "bg-info/10 text-info"
    case "failed":
    case "error":
      return "bg-destructive/10 text-destructive"
    case "paused":
      return "bg-warning/10 text-warning"
    default:
      return "bg-secondary text-muted-foreground"
  }
}

// Agent Orb Component - Premium visual personality representation with depth
function AgentOrb({ agent, isSelected, onClick, index }: { agent: Agent; isSelected: boolean; onClick: () => void; index: number }) {
  const { reduced } = useMotionPrefs()
  const status = statusConfig[agent.status]

  // Shared identity gradient (stored icon/color when present, otherwise department fallback).
  const identity = resolveAgentIdentity(agent)
  const { gradient, glow } = identity.personality
  const isLive = agent.status === "active" || agent.status === "processing"

  return (
    <motion.button
      type="button"
      onClick={onClick}
      layout
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: 30, scale: 0.8 }}
      animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.15 } }}
      transition={reduced ? { duration: 0.12 } : { delay: Math.min(index, 8) * 0.05, type: "spring", stiffness: 100 }}
      whileHover={reduced ? undefined : { scale: 1.02, y: -3 }}
      whileTap={reduced ? undefined : { scale: 0.98 }}
      className={cn(
        "relative group flex w-[168px] sm:w-[184px] shrink-0 snap-center flex-col items-center rounded-2xl border border-transparent px-3 py-4 text-left transition-[colors,box-shadow] duration-200",
        isSelected
          ? "border-primary/30 bg-card/70 shadow-lg z-10"
          : "hover:border-border/60 hover:bg-card/40 hover:shadow-xl hover:shadow-black/20",
        agent.status === "idle" && "opacity-85",
      )}
    >
      {/* Soft colored halo behind the orb */}
      <motion.div
        aria-hidden
        className={cn("pointer-events-none absolute inset-x-4 top-6 h-24 rounded-full blur-2xl bg-gradient-to-br", gradient)}
        animate={{ opacity: isSelected ? 0.35 : 0.18 }}
      />

      <div className="relative mb-4 flex h-28 w-28 items-center justify-center">
        {(agent.status === "active" || agent.status === "processing") && !reduced && (
          <>
            <motion.div
              className={cn(
                "absolute inset-0 rounded-full border-2",
                agent.status === "processing" ? "border-info/40" : "border-success/30",
              )}
              animate={{ scale: [1, 1.22, 1], opacity: [0.6, 0, 0.6] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut" }}
            />
            <motion.div
              className={cn(
                "absolute inset-0 rounded-full border",
                agent.status === "processing" ? "border-info/20" : "border-success/20",
              )}
              animate={{ scale: [1, 1.35, 1], opacity: [0.4, 0, 0.4] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut", delay: 0.5 }}
            />
          </>
        )}

        {agent.model ? (
          <AgentModelBadge
            model={agent.model}
            variant="orb"
            className="absolute -top-1 right-0 z-20 max-w-[92px] truncate rounded-full border border-border bg-card/95 px-2 py-0.5 text-[9px] font-medium text-muted-foreground shadow-sm transition-colors group-hover:border-foreground/20 group-hover:text-foreground"
          />
        ) : null}

        {Boolean(agent.config?.marketplaceAssetId) ? (
          <span className="absolute -bottom-1 left-1/2 z-20 -translate-x-1/2 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-primary shadow-sm">
            Marketplace
          </span>
        ) : null}

        {agent.stats.tasksToday > 0 && (
          <div className="absolute -top-1 left-0 z-20 flex h-6 min-w-6 items-center justify-center rounded-full border border-border bg-card px-1 shadow-lg">
            <span className="text-[10px] font-bold text-foreground">
              {agent.stats.tasksToday > 99 ? "99+" : agent.stats.tasksToday}
            </span>
          </div>
        )}

        <div className="relative" style={{ transform: "translateZ(20px)" }}>
          <AgentIdentityAvatar
            agent={agent}
            size="orb"
            className={cn(
              isSelected ? "ring-2 ring-foreground/15" : "",
              agent.status === "error" && "opacity-50 grayscale-[30%]",
            )}
          />
          {agent.status === "processing" && !reduced && (
            <motion.div
              className="absolute inset-0 rounded-full border-[3px] border-white/20 border-t-white"
              animate={{ rotate: 360 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
            />
          )}
          {agent.status === "error" && (
            <div className="absolute inset-0 flex items-center justify-center rounded-full bg-destructive/30">
              <Shield className="h-5 w-5 text-white" />
            </div>
          )}
        </div>
      </div>

      <div className="relative z-10 w-full space-y-2 text-center">
        <div className="space-y-0.5">
          <p className="truncate text-sm font-semibold text-foreground">{agent.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{agent.role}</p>
        </div>

        {/* Success rate · tasks today */}
        <p className="text-[10px] text-muted-foreground">
          {shouldShowSuccessRate(agent) ? (
            <span className={successRateColorClass(agent.stats.successRate)}>{agent.stats.successRate}%</span>
          ) : (
            <span className="text-muted-foreground/70">No tasks yet</span>
          )}
          <span className="mx-1">·</span>
          <span>{agent.stats.tasksToday} today</span>
        </p>

        {/* Status pill — instant active/idle/error read */}
        <div
          className={cn(
            "relative mx-auto flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1",
            agent.status === "error"
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : agent.status === "processing"
                ? "border-info/30 bg-info/10 text-info"
                : agent.status === "active"
                  ? "border-success/40 bg-success/10 text-success"
                  : "border-border bg-muted text-muted-foreground",
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
            pulse={isLive}
          />
          <span className="text-[10px] font-semibold uppercase tracking-wider">{status.label}</span>
        </div>

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
            <AgentIdentityAvatar agent={agent} size="lg" />
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
              aria-label={`Configure ${agent.name}`}
            >
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">{agent.description}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className={cn(
            "rounded-md px-2 py-1 text-xs font-medium",
            shouldShowSuccessRate(agent)
              ? successRateBadgeClass(agent.stats.successRate)
              : "bg-secondary text-muted-foreground",
          )}>
            {shouldShowSuccessRate(agent) ? `${agent.stats.successRate}% success` : "No tasks yet"}
          </span>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs text-muted-foreground">
            {agent.stats.tasksToday} tasks
          </span>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs text-muted-foreground">
            {agent.stats.avgResponseTime} avg
          </span>
          {agent.model ? (
            <AgentModelBadge
              model={agent.model}
              variant="panel"
              className="max-w-[140px] truncate rounded-md border border-border px-2 py-1 text-xs text-muted-foreground"
            />
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
            shouldShowSuccessRate(agent)
              ? successRateColorClass(agent.stats.successRate)
              : "text-muted-foreground",
          )}>
            {shouldShowSuccessRate(agent) ? `${agent.stats.successRate}%` : "—"}
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
          agent.status === "error" ? "border-destructive/30 bg-destructive/5" : "border-border bg-secondary/30"
        )}>
          <div className="flex items-start gap-3">
            <div className={cn(
              "h-8 w-8 rounded-full flex items-center justify-center",
              agent.status === "error" ? "bg-destructive/10" : "bg-info/10"
            )}>
              {agent.status === "processing" ? (
                <Activity className="h-4 w-4 text-info animate-pulse" />
              ) : agent.status === "error" ? (
                <Shield className="h-4 w-4 text-destructive" />
              ) : (
                <Zap className="h-4 w-4 text-info" />
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

function AgentPreviewSheet({
  agent,
  open,
  onOpenChange,
  onOpenProfile,
}: {
  agent: Agent
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenProfile: () => void
}) {
  const recentTasks = getAgentRecentTasks(agent)
  const status = statusConfig[agent.status]

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto p-0 sm:max-w-sm">
        <SheetHeader className="space-y-3 border-b border-border px-5 py-5 text-left">
          <div className="flex items-start gap-3">
            <AgentIdentityAvatar agent={agent} size="md" />
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate text-base">{agent.name}</SheetTitle>
              <SheetDescription className="truncate">{agent.role}</SheetDescription>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                agent.status === "error"
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : agent.status === "processing"
                    ? "border-info/30 bg-info/10 text-info"
                    : agent.status === "active"
                      ? "border-success/30 bg-success/10 text-success"
                      : "border-border bg-secondary text-muted-foreground",
              )}
            >
              {status.label}
            </span>
            {agent.model ? (
              <AgentModelBadge
                model={agent.model}
                variant="panel"
                className="max-w-[140px] truncate rounded-md border border-border px-2 py-0.5 text-[10px] text-muted-foreground"
              />
            ) : null}
          </div>
        </SheetHeader>

        <div className="space-y-4 px-5 py-4">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg border border-border bg-card/60 px-2 py-3 text-center">
              <div className="text-lg font-semibold text-foreground">{agent.stats.tasksToday}</div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Tasks</div>
            </div>
            <div className="rounded-lg border border-border bg-card/60 px-2 py-3 text-center">
              <div className="text-lg font-semibold text-foreground">
                {shouldShowSuccessRate(agent) ? `${agent.stats.successRate}%` : "—"}
              </div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Success</div>
            </div>
            <div className="rounded-lg border border-border bg-card/60 px-2 py-3 text-center">
              <div className="text-lg font-semibold text-foreground">{agent.stats.workflowsUsing}</div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Flows</div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Recent activity</p>
            {recentTasks.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {recentTasks.slice(0, 3).map((task) => (
                  <li key={task.id} className="flex items-center gap-2 text-xs">
                    <Zap className="h-3 w-3 shrink-0 text-info/80" />
                    <span className="min-w-0 flex-1 truncate text-foreground">{task.title}</span>
                    <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[9px] font-medium uppercase", taskStatusBadgeClass(task.status))}>
                      {task.status}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">No recent tasks for this agent yet.</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Button variant="outline" className="w-full gap-1.5" asChild>
              <a href={`/agents/${agent.id}/chat`}>
                <MessageSquare className="h-3.5 w-3.5" />
                Chat
              </a>
            </Button>
            <Button className="w-full gap-1.5" asChild>
              <a href={`/lite/assign?agent=${agent.id}`}>
                <Play className="h-3.5 w-3.5" />
                Assign Task
              </a>
            </Button>
            <Button variant="ghost" className="w-full" onClick={onOpenProfile}>
              View full profile
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function MesonBuildButton({
  onClick,
  isOpen,
}: {
  onClick: () => void
  isOpen?: boolean
}) {
  const { reduced } = useMotionPrefs()

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="group relative">
            <div
              aria-hidden
              className={cn(
                "pointer-events-none absolute -inset-px rounded-lg bg-gradient-to-r from-violet-500/60 via-fuchsia-500/40 to-indigo-500/60 opacity-60 blur-[2px] transition-opacity duration-300",
                "group-hover:opacity-100 group-focus-within:opacity-100",
                isOpen && "opacity-100",
              )}
            />
            <motion.div
              whileHover={reduced ? undefined : { scale: 1.02 }}
              whileTap={reduced ? undefined : { scale: 0.98 }}
              className={cn(
                "relative rounded-lg bg-gradient-to-r from-violet-500/50 via-fuchsia-500/30 to-indigo-500/50 p-px shadow-lg shadow-violet-500/15",
                isOpen && "shadow-violet-500/25",
              )}
            >
              <Button
                type="button"
                variant="ghost"
                onClick={onClick}
                aria-expanded={isOpen}
                aria-haspopup="dialog"
                aria-label="Build with Meson"
                className={cn(
                  "relative gap-2 rounded-[7px] border-0 bg-card/95 px-3 hover:bg-violet-500/10",
                  isOpen && "bg-violet-500/15",
                )}
              >
                <motion.span
                  animate={
                    reduced
                      ? undefined
                      : { rotate: [0, 10, -10, 0], scale: [1, 1.08, 1] }
                  }
                  transition={
                    reduced
                      ? undefined
                      : { duration: 2.8, repeat: Infinity, ease: "easeInOut" }
                  }
                  className="inline-flex"
                >
                  <Sparkles className="h-4 w-4 text-violet-400" />
                </motion.span>
                <span className="hidden bg-gradient-to-r from-violet-300 via-fuchsia-300 to-indigo-300 bg-clip-text font-medium text-transparent sm:inline">
                  Build with Meson
                </span>
                <span className="bg-gradient-to-r from-violet-300 via-fuchsia-300 to-indigo-300 bg-clip-text text-sm font-medium text-transparent sm:hidden">
                  Meson
                </span>
              </Button>
            </motion.div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          AI-powered builder — describe intent, deploy agents and workflows
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
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

  // Collapse the team-overview hero (title + stat cards) to give the user a
  // clear, full-height canvas of just the agents. Persisted across visits.
  const [headerCollapsed, setHeaderCollapsed] = useState(() => {
    if (typeof window === "undefined") return false
    return window.localStorage.getItem(AGENT_HEADER_COLLAPSED_KEY) === "1"
  })

  const toggleHeaderCollapsed = () => {
    setHeaderCollapsed((collapsed) => {
      const next = !collapsed
      window.localStorage.setItem(AGENT_HEADER_COLLAPSED_KEY, next ? "1" : "0")
      return next
    })
  }
  
  // Fetch agents from API with SWR — refresh every 30s for live task/active counts
  const { data, error, isLoading, mutate } = useSWR<{ agents: Agent[] }>(
    user ? "/api/agents" : null,
    apiFetcher,
    {
      revalidateOnFocus: true,
      revalidateOnMount: true,
      refreshInterval: AGENTS_REFRESH_MS,
      dedupingInterval: 2000,
      onError: (err) => {
        console.error("[v0] Agents fetch error:", err)
      },
    }
  )
  
  const agents = normalizeAgentsResponse(data)
  
  const searchInputRef = useRef<HTMLInputElement>(null)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [mesonWizardOpen, setMesonWizardOpen] = useState(false)

  const normalizedSearchQuery = searchQuery.trim().toLowerCase()

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable) return
      event.preventDefault()
      searchInputRef.current?.focus()
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  useWorkPageShortcut("focus-search", () => searchInputRef.current?.focus())

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
  
  const filteredAgents = useMemo(() => {
    if (!normalizedSearchQuery) return agents
    return agents.filter((agent) => agentMatchesQuery(agent, normalizedSearchQuery))
  }, [agents, normalizedSearchQuery])

  const visibleSelectedAgent = useMemo(() => {
    if (selectedAgent && filteredAgents.some((agent) => agent.id === selectedAgent.id)) {
      return selectedAgent
    }
    return null
  }, [selectedAgent, filteredAgents])

  const activeCount = agents.filter((a) => a.status === "active" || a.status === "processing").length
  const totalTasks = agents.reduce((sum, a) => sum + a.stats.tasksToday, 0)
  const totalAgents = agents.length

  const prevActiveCountRef = useRef(activeCount)
  const [activeStatPulse, setActiveStatPulse] = useState(false)

  useEffect(() => {
    if (prevActiveCountRef.current === activeCount) return
    prevActiveCountRef.current = activeCount
    setActiveStatPulse(true)
    const timer = window.setTimeout(() => setActiveStatPulse(false), 800)
    return () => window.clearTimeout(timer)
  }, [activeCount])

  const rosterActions = (
    <>
      <MesonBuildButton
        onClick={() => setMesonWizardOpen(true)}
        isOpen={mesonWizardOpen}
      />
      <Button variant="outline" onClick={() => router.push(APP_ROUTES.multiAgentRun)} className="gap-2">
        <Users className="h-4 w-4" />
        <span className="hidden sm:inline">Multi-Agent Run</span>
      </Button>
      <Button onClick={() => router.push("/agents/new")} className="gap-2 bg-zinc-900 hover:bg-zinc-800 text-white">
        <Plus className="h-4 w-4" />
        <span className="hidden sm:inline">New Agent</span>
      </Button>
      {visibleSelectedAgent ? (
        <Button
          variant="outline"
          size="icon"
          onClick={toggleDetailPanel}
          aria-label={detailPanelOpen ? "Hide agent details" : "Show agent details"}
          className="hidden lg:inline-flex"
        >
          {detailPanelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
        </Button>
      ) : null}
    </>
  )

  return (
  <AppShell title={SURFACE_COPY.pages.agents.title}>
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
          <div className="relative z-10 px-4 pt-4 md:px-6 space-y-3">
            <Suspense fallback={null}>
              <AgentsHubTabs active="roster" />
            </Suspense>
            <AgentSurfaceSwitch surface="operate" />
          </div>
          {/* Collapse only hides overview title/stats — primary CTAs stay reachable. */}
          {!headerCollapsed ? (
            <PageHeader
              title={SURFACE_COPY.pages.agents.rosterTitle}
              description={SURFACE_COPY.pages.agents.description}
              icon={Brain}
              iconColor="from-violet-500/20 to-purple-500/20"
              actions={rosterActions}
            >
              <StatsGrid columns={3}>
                <StatCard
                  label="Total"
                  value={<AnimatedCounter value={totalAgents} duration={0.8} />}
                />
                <motion.div
                  animate={
                    activeStatPulse
                      ? { scale: [1, 1.04, 1], boxShadow: ["0 0 0 rgba(16,185,129,0)", "0 0 20px rgba(16,185,129,0.25)", "0 0 0 rgba(16,185,129,0)"] }
                      : { scale: 1 }
                  }
                  transition={{ duration: 0.6, ease: "easeOut" }}
                  className="rounded-lg"
                >
                  <StatCard
                    label="Active"
                    value={<AnimatedCounter value={activeCount} duration={0.8} />}
                    variant="success"
                    className={activeCount > 0 ? "border-success/30" : undefined}
                  />
                </motion.div>
                <StatCard
                  label="Tasks"
                  value={<AnimatedCounter value={totalTasks} duration={1} />}
                  variant="info"
                />
              </StatsGrid>
            </PageHeader>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 bg-background/40 px-3 py-2.5 backdrop-blur-sm sm:px-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold tracking-tight text-foreground">
                  {SURFACE_COPY.pages.agents.rosterTitle}
                </p>
                <p className="text-xs text-muted-foreground">
                  {activeCount} active · {totalAgents} total · {totalTasks} tasks today
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">{rosterActions}</div>
            </div>
          )}

          {/* Search */}
          <div className="p-3 sm:p-4 border-b border-border space-y-2">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  ref={searchInputRef}
                  type="search"
                  placeholder="Search agents by name, role, department..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search agents"
                  className="w-full h-10 sm:h-9 rounded-lg border border-border bg-secondary pl-9 pr-9 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                />
                {searchQuery ? (
                  <button
                    type="button"
                    aria-label="Clear search"
                    onClick={() => {
                      setSearchQuery("")
                      searchInputRef.current?.focus()
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                ) : null}
              </div>
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={toggleHeaderCollapsed}
                aria-label={headerCollapsed ? "Show team overview" : "Hide team overview for a clear agent canvas"}
                aria-expanded={!headerCollapsed}
                title={headerCollapsed ? "Show team overview" : "Clear canvas"}
                className="h-10 w-10 shrink-0 sm:h-9 sm:w-9"
              >
                {headerCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
              </Button>
            </div>
            {normalizedSearchQuery && agents.length > 0 ? (
              <p className="text-xs text-muted-foreground">
                {filteredAgents.length} of {agents.length} agent{agents.length === 1 ? "" : "s"}
              </p>
            ) : null}
          </div>

          {/* Agent Orb Grid - Premium with particle field */}
          <div className="relative flex flex-1 flex-col p-4 sm:p-8 overflow-y-auto overflow-x-hidden">
            {/* Particle field behind orbs */}
            <ParticleField count={30} color="violet" interactive className="opacity-40" />
            
            {/* Center stage area. On mobile it keeps a fixed-height band for the
               horizontal carousel; on desktop it grows with content (min-h-0) so
               a tall, wrapped constellation flows from the top and scrolls in the
               parent instead of being vertically centered and clipped. */}
            <div className="relative flex flex-1 flex-col min-h-[420px] sm:min-h-0">
              {/* Circular platform effect (clipped so the large rings never force
                 horizontal overflow on narrow/mobile viewports). */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden">
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
              
              {/* Orb constellation.
                 Mobile: a single-row horizontal swipe carousel, vertically
                 centered in the fixed-height band (my-auto).
                 Desktop: a wrapping constellation that flows from the top
                 (sm:my-0, sm:items-start) and scrolls naturally — no vertical
                 centering, so tall multi-row layouts are never clipped. */}
              <TooltipProvider delayDuration={200}>
              <div className={cn(
                "relative z-10 flex w-full gap-6 sm:gap-10 lg:gap-12",
                // Mobile carousel. overflow-x-auto forces overflow-y to clip, so
                // full-height orbs are centered within the tall band.
                "my-auto flex-nowrap items-center snap-x snap-mandatory overflow-x-auto scrollbar-hide px-4 -mx-4 py-6",
                // sm+: wrapping constellation, top-aligned, generous padding so
                // orb badges/labels are never clipped by the scroll container.
                "sm:my-0 sm:flex-wrap sm:items-start sm:justify-center sm:overflow-x-visible sm:px-0 sm:mx-0 sm:snap-none sm:py-10",
              )}>
                {error ? (
                  <WorkSectionErrorCard
                    title="Could not load agents"
                    message="We couldn't reach the agents service. Check your connection and try again."
                    onRetry={() => void mutate()}
                    className="mx-auto max-w-sm"
                  />
                ) : isLoading && agents.length === 0 ? (
                  <div className="mx-auto flex flex-wrap justify-center gap-8 sm:gap-10 lg:gap-12 pt-8 sm:pt-10 pb-28">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <div key={index} className="flex flex-col items-center gap-3">
                        <Skeleton className="h-24 w-24 rounded-full" />
                        <Skeleton className="h-3 w-20" />
                        <Skeleton className="h-2 w-16" />
                      </div>
                    ))}
                  </div>
                ) : filteredAgents.length === 0 ? (
                  <div className="mx-auto text-center space-y-3 px-4">
                    {normalizedSearchQuery ? (
                      <>
                        <Bot className="mx-auto h-10 w-10 text-muted-foreground/40" />
                        <p className="text-sm text-muted-foreground">
                          No agents matching &apos;{searchQuery.trim()}&apos;
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSearchQuery("")
                            searchInputRef.current?.focus()
                          }}
                        >
                          Clear search
                        </Button>
                      </>
                    ) : (
                      <>
                        <p className="text-sm text-muted-foreground">
                          No agents yet. Create your first AI teammate.
                        </p>
                        <Button onClick={() => router.push("/agents/new")} className="gap-2">
                          <Plus className="h-4 w-4" />
                          New Agent
                        </Button>
                      </>
                    )}
                  </div>
                ) : (
                  <AnimatePresence mode="popLayout">
                    {filteredAgents.map((agent, index) => (
                      <AgentOrb
                        key={agent.id}
                        agent={agent}
                        index={index}
                        isSelected={visibleSelectedAgent?.id === agent.id}
                        onClick={() => {
                          setSelectedAgent(agent)
                          setPreviewOpen(true)
                        }}
                      />
                    ))}
                  </AnimatePresence>
                )}
              </div>
              </TooltipProvider>
            </div>
          </div>
        </div>

        {visibleSelectedAgent ? (
          <AgentPreviewSheet
            agent={visibleSelectedAgent}
            open={previewOpen}
            onOpenChange={setPreviewOpen}
            onOpenProfile={() => router.push(`/agents/${visibleSelectedAgent.id}`)}
          />
        ) : null}

{/* Right - Agent Detail Panel - Premium glassmorphism */}
        <AnimatePresence initial={false}>
          {/* Only reserve the side-panel width when there is actually an agent
             to show. Previously the panel defaulted open and reserved 420px even
             with no selection, leaving a large empty panel that squeezed the orb
             stage into a narrow strip. */}
          {detailPanelOpen && visibleSelectedAgent ? (
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
                <TooltipProvider delayDuration={200}>
                  <AgentDetailPanel
                    key={visibleSelectedAgent.id}
                    agent={visibleSelectedAgent}
                    onStart={handleStartAgent}
                    onStop={handleStopAgent}
                    isMutating={isMutatingAgent === visibleSelectedAgent.id}
                  />
                </TooltipProvider>
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
