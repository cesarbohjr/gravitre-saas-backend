"use client"

// Agents Page - AI Team Command Center with Premium Orb System
import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
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
  Circle,
  Workflow,
  Shield,
  Blocks,
  type LucideIcon
} from "lucide-react"
import { cn } from "@/lib/utils"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { fetcher } from "@/lib/fetcher"

interface Agent {
  id: string
  name: string
  role: string
  department: "Marketing" | "Sales" | "Operations" | "Finance" | "Support"
  description: string
  status: "active" | "idle" | "processing" | "error"
  personality: {
    color: string
    gradient: string
    glow: string
  }
  stats: {
    tasksToday: number
    successRate: number
    avgResponseTime: string
    workflowsUsing: number
  }
  capabilities: string[]
  permissions: string[]
  lastAction: string
  lastActionTime: string
}

const fallbackAgents: Agent[] = [
  {
    id: "agent-001",
    name: "Atlas",
    role: "Marketing Operator",
    department: "Marketing",
    description: "Orchestrates marketing campaigns and analyzes performance metrics",
    status: "active",
    personality: {
      color: "emerald",
      gradient: "from-emerald-500 to-teal-500",
      glow: "shadow-emerald-500/30",
    },
    stats: {
      tasksToday: 147,
      successRate: 98.2,
      avgResponseTime: "1.2s",
      workflowsUsing: 4,
    },
    capabilities: ["Campaign analysis", "Report generation", "A/B testing", "Email sequences", "Content creation"],
    permissions: ["HubSpot", "Google Analytics", "Mailchimp", "LinkedIn Ads"],
    lastAction: "Generated weekly performance report",
    lastActionTime: "2 minutes ago",
  },
  {
    id: "agent-002",
    name: "Nexus",
    role: "Sales Assistant",
    department: "Sales",
    description: "Syncs customer data and provides real-time sales insights",
    status: "processing",
    personality: {
      color: "blue",
      gradient: "from-blue-500 to-indigo-500",
      glow: "shadow-blue-500/30",
    },
    stats: {
      tasksToday: 234,
      successRate: 99.1,
      avgResponseTime: "0.8s",
      workflowsUsing: 6,
    },
    capabilities: ["Contact sync", "Deal tracking", "Forecast modeling", "Lead scoring", "Outreach sequences"],
    permissions: ["Salesforce", "HubSpot CRM", "LinkedIn Sales Nav", "Outreach.io"],
    lastAction: "Syncing 1,247 contacts from Salesforce",
    lastActionTime: "Now",
  },
  {
    id: "agent-003",
    name: "Sentinel",
    role: "Data Quality Agent",
    department: "Operations",
    description: "Monitors data integrity and detects anomalies in real-time",
    status: "idle",
    personality: {
      color: "amber",
      gradient: "from-amber-500 to-orange-500",
      glow: "shadow-amber-500/30",
    },
    stats: {
      tasksToday: 56,
      successRate: 100,
      avgResponseTime: "2.1s",
      workflowsUsing: 2,
    },
    capabilities: ["Anomaly detection", "Schema validation", "Deduplication", "Data enrichment"],
    permissions: ["Snowflake", "BigQuery", "PostgreSQL", "AWS S3"],
    lastAction: "Validated 50,000 records",
    lastActionTime: "15 minutes ago",
  },
  {
    id: "agent-004",
    name: "Oracle",
    role: "Finance Reporter",
    department: "Finance",
    description: "Generates financial reports and tracks budget metrics",
    status: "active",
    personality: {
      color: "violet",
      gradient: "from-violet-500 to-purple-500",
      glow: "shadow-violet-500/30",
    },
    stats: {
      tasksToday: 23,
      successRate: 100,
      avgResponseTime: "3.4s",
      workflowsUsing: 2,
    },
    capabilities: ["Report generation", "Budget analysis", "Trend forecasting", "Expense tracking"],
    permissions: ["QuickBooks", "NetSuite", "Excel", "Tableau"],
    lastAction: "Compiled Q4 expense summary",
    lastActionTime: "1 hour ago",
  },
  {
    id: "agent-005",
    name: "Harbor",
    role: "Support Coordinator",
    department: "Support",
    description: "Routes tickets and tracks SLA compliance",
    status: "error",
    personality: {
      color: "rose",
      gradient: "from-rose-500 to-pink-500",
      glow: "shadow-rose-500/30",
    },
    stats: {
      tasksToday: 0,
      successRate: 0,
      avgResponseTime: "-",
      workflowsUsing: 3,
    },
    capabilities: ["Ticket routing", "SLA tracking", "Escalation handling", "Customer sentiment"],
    permissions: ["Zendesk", "Intercom", "Freshdesk", "Slack"],
    lastAction: "Connection to Zendesk failed",
    lastActionTime: "30 minutes ago",
  },
]

const roleIcons: Record<string, LucideIcon> = {
  "Marketing Operator": Megaphone,
  "Sales Assistant": TrendingUp,
  "Data Quality Agent": Database,
  "Finance Reporter": PieChart,
  "Support Coordinator": Headphones,
}

const statusConfig = {
  active: { label: "Active", color: "text-emerald-400", dotColor: "bg-emerald-500", animate: true },
  idle: { label: "Idle", color: "text-zinc-400", dotColor: "bg-zinc-500", animate: false },
  processing: { label: "Processing", color: "text-blue-400", dotColor: "bg-blue-500", animate: true },
  error: { label: "Error", color: "text-red-400", dotColor: "bg-red-500", animate: false },
}

function mapDepartment(input: string | null | undefined): Agent["department"] {
  if (!input) return "Operations"
  if (input.includes("marketing")) return "Marketing"
  if (input.includes("sales")) return "Sales"
  if (input.includes("finance")) return "Finance"
  if (input.includes("support")) return "Support"
  return "Operations"
}

function mapStatus(input: string | null | undefined): Agent["status"] {
  if (!input) return "idle"
  if (input === "active") return "active"
  if (input === "running" || input === "processing" || input === "planning") return "processing"
  if (input === "error" || input === "failed" || input === "inactive") return "error"
  return "idle"
}

function fallbackPersonality(index: number) {
  const variants = [
    { color: "emerald", gradient: "from-emerald-500 to-teal-500", glow: "shadow-emerald-500/30" },
    { color: "blue", gradient: "from-blue-500 to-indigo-500", glow: "shadow-blue-500/30" },
    { color: "amber", gradient: "from-amber-500 to-orange-500", glow: "shadow-amber-500/30" },
    { color: "violet", gradient: "from-violet-500 to-purple-500", glow: "shadow-violet-500/30" },
    { color: "rose", gradient: "from-rose-500 to-pink-500", glow: "shadow-rose-500/30" },
  ] as const
  return variants[index % variants.length]
}

function mapOperatorsToAgents(operators: Array<Record<string, unknown>> | undefined): Agent[] {
  if (!operators || operators.length === 0) return fallbackAgents
  return operators.map((operator, index) => {
    const config = (operator.config ?? {}) as Record<string, unknown>
    const role = String(operator.role ?? "AI Agent")
    const description = String(operator.description ?? "AI teammate")
    const capabilities = Array.isArray(operator.capabilities)
      ? (operator.capabilities as string[])
      : []
    const connectors = Array.isArray(operator.connectors)
      ? (operator.connectors as Array<{ vendor?: string; name?: string }>).map(
          (connector) => connector.vendor ?? connector.name ?? "System"
        )
      : []
    const personality = fallbackPersonality(index)
    const status = mapStatus(String(operator.status ?? "idle"))
    const lastAction = String(config.last_action ?? "No recent activity")
    const lastActionTime = String(config.last_action_time ?? "recently")
    return {
      id: String(operator.id ?? `agent-${index}`),
      name: String(operator.name ?? `Agent ${index + 1}`),
      role,
      department: mapDepartment(role.toLowerCase()),
      description,
      status,
      personality,
      stats: {
        tasksToday: Number(config.tasks_today ?? 0),
        successRate: Number(config.success_rate ?? (status === "error" ? 0 : 100)),
        avgResponseTime: String(config.avg_response_time ?? "-"),
        workflowsUsing: Number(config.workflows_using ?? operator.link_count ?? 0),
      },
      capabilities,
      permissions: connectors,
      lastAction,
      lastActionTime,
    }
  })
}

// Agent Orb Component - Premium visual personality representation with depth
function AgentOrb({ agent, isSelected, onClick, index }: { agent: Agent; isSelected: boolean; onClick: () => void; index: number }) {
  const Icon = roleIcons[agent.role] || Bot
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
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      initial={{ opacity: 0, y: 30, scale: 0.8 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.1, type: "spring", stiffness: 100 }}
      whileHover={{ scale: 1.08, y: -8 }}
      whileTap={{ scale: 0.95 }}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
      className={cn(
        "relative group perspective-1000",
        isSelected && "z-10"
      )}
    >
      {/* Ambient glow - subtle for selected */}
      <motion.div 
        className={cn(
          "absolute -inset-3 rounded-full blur-xl transition-opacity duration-500",
          `bg-gradient-to-br ${agent.personality.gradient}`
        )}
        animate={{ opacity: isSelected ? 0.25 : 0, scale: isSelected ? 1.1 : 1 }}
      />
      
      {/* Outer glow ring on hover - very subtle */}
      <div className={cn(
        "absolute -inset-2 rounded-full opacity-0 group-hover:opacity-30 transition-opacity duration-300 blur-lg",
        `bg-gradient-to-br ${agent.personality.gradient}`
      )} />
      
      {/* Animated pulse rings for active/processing */}
      {(agent.status === "active" || agent.status === "processing") && (
        <>
          <motion.div
            className={cn(
              "absolute -inset-2 rounded-full border-2",
              agent.status === "processing" ? "border-blue-500/40" : "border-emerald-500/30"
            )}
            animate={{ scale: [1, 1.3, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut" }}
          />
          <motion.div
            className={cn(
              "absolute -inset-2 rounded-full border",
              agent.status === "processing" ? "border-blue-500/20" : "border-emerald-500/20"
            )}
            animate={{ scale: [1, 1.5, 1], opacity: [0.4, 0, 0.4] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeOut", delay: 0.5 }}
          />
        </>
      )}

      {/* Main orb with inner depth */}
      <div 
        className={cn(
          "relative h-28 w-28 rounded-full flex items-center justify-center transition-all duration-300",
          `bg-gradient-to-br ${agent.personality.gradient}`,
          isSelected ? "ring-2 ring-white/20 shadow-lg scale-105" : "shadow-md",
          agent.status === "error" && "opacity-50 grayscale-[30%]"
        )}
        style={{ transform: "translateZ(20px)" }}
      >
        {/* Inner highlight */}
        <div className="absolute inset-2 rounded-full bg-gradient-to-br from-white/20 to-transparent" />
        
        {/* Icon */}
        <Icon className="h-11 w-11 text-white drop-shadow-lg relative z-10" />
        
        {/* Processing spinner */}
        {agent.status === "processing" && (
          <motion.div
            className="absolute inset-0 rounded-full border-3 border-white/20 border-t-white"
            animate={{ rotate: 360 }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
          />
        )}
        
        {/* Error X overlay */}
        {agent.status === "error" && (
          <div className="absolute inset-0 rounded-full bg-red-900/30 flex items-center justify-center">
            <Shield className="h-6 w-6 text-red-400 absolute top-2 right-2" />
          </div>
        )}
      </div>

      {/* Name label - positioned below orb */}
      <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-center whitespace-nowrap z-10">
        <p className="text-sm font-semibold text-foreground">{agent.name}</p>
        <p className="text-[10px] text-muted-foreground">{agent.role}</p>
      </div>
      
      {/* Status indicator - positioned below name */}
      <motion.div 
        className={cn(
          "absolute -bottom-[4.5rem] left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-2.5 py-1 rounded-full backdrop-blur-sm border shadow-lg z-20",
          agent.status === "error" 
            ? "bg-red-500/90 border-red-500/50 text-white" 
            : agent.status === "processing"
              ? "bg-blue-500/20 border-blue-500/30"
              : agent.status === "active"
                ? "bg-emerald-500/20 border-emerald-500/30"
                : "bg-card/80 border-border"
        )}
        initial={{ opacity: 0, y: -5 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.1 + 0.2 }}
      >
        <StatusBeacon 
          status={agent.status === "error" ? "error" : agent.status === "processing" ? "processing" : agent.status === "active" ? "active" : "idle"} 
          size="sm" 
          pulse={agent.status !== "idle"}
        />
        <span className={cn(
          "text-[10px] font-semibold uppercase tracking-wider",
          agent.status === "error" ? "text-white" : status.color
        )}>
          {status.label}
        </span>
      </motion.div>
      
      {/* Task count badge */}
      {agent.stats.tasksToday > 0 && (
        <motion.div 
          className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-card border border-border flex items-center justify-center shadow-lg"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: index * 0.1 + 0.3 }}
        >
          <span className="text-[10px] font-bold text-foreground">{agent.stats.tasksToday > 99 ? "99+" : agent.stats.tasksToday}</span>
        </motion.div>
      )}
    </motion.button>
  )
}

// Agent Detail Panel
function AgentDetailPanel({ agent }: { agent: Agent }) {
  const router = useRouter()
  const Icon = roleIcons[agent.role] || Bot
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
              <Icon className="h-7 w-7 text-white" />
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
              <Button variant="outline" size="sm" className="gap-2">
                <Pause className="h-3.5 w-3.5" />
                Pause
              </Button>
            ) : agent.status !== "error" ? (
              <Button size="sm" className="gap-2 bg-zinc-900 hover:bg-zinc-800 text-white">
                <Play className="h-3.5 w-3.5" />
                Activate
              </Button>
            ) : (
              <Button variant="destructive" size="sm" className="gap-2">
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
            <div 
              key={i}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary border border-border"
            >
              <Sparkles className="h-3 w-3 text-muted-foreground" />
              <span className="text-sm text-foreground">{cap}</span>
            </div>
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
            <div 
              key={i}
              className="px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/20"
            >
              <span className="text-xs text-blue-400">{perm}</span>
            </div>
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
  const { data, mutate } = useSWR<{ operators?: Array<Record<string, unknown>> }>(
    "/api/agents",
    fetcher,
    { revalidateOnFocus: false }
  )
  const agents = useMemo(() => mapOperatorsToAgents(data?.operators), [data?.operators])
  const [selectedAgent, setSelectedAgent] = useState<Agent>(agents[0] ?? fallbackAgents[0])
  const [searchQuery, setSearchQuery] = useState("")
  const [mesonWizardOpen, setMesonWizardOpen] = useState(false)

  useEffect(() => {
    if (!selectedAgent && agents.length > 0) {
      setSelectedAgent(agents[0])
      return
    }
    if (selectedAgent && !agents.some((agent) => agent.id === selectedAgent.id) && agents.length > 0) {
      setSelectedAgent(agents[0])
    }
  }, [agents, selectedAgent])

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
              <div className="relative flex flex-wrap gap-10 sm:gap-14 lg:gap-20 justify-center items-center pt-8 sm:pt-12 pb-8">
                {filteredAgents.map((agent, index) => (
                  <AgentOrb
                    key={agent.id}
                    agent={agent}
                    index={index}
                    isSelected={selectedAgent?.id === agent.id}
                    onClick={() => setSelectedAgent(agent)}
                  />
                ))}
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
        <div className="relative z-10 lg:w-[420px] bg-card/40 backdrop-blur-xl border-t lg:border-t-0 lg:border-l border-border/50 shadow-2xl">
          {/* Gradient accent */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-blue-500 to-emerald-500" />
          <AnimatePresence mode="wait">
            {selectedAgent ? <AgentDetailPanel key={selectedAgent.id} agent={selectedAgent} /> : null}
          </AnimatePresence>
        </div>
      </div>

      {/* Meson Wizard */}
      <MesonWizard 
        open={mesonWizardOpen} 
        onClose={() => setMesonWizardOpen(false)}
        onComplete={async (result) => {
          const payload = {
            name: String(result?.name ?? "New Agent"),
            description: String(result?.description ?? "Created from Meson wizard"),
            role: String(result?.role ?? "AI Agent"),
            capabilities: Array.isArray(result?.capabilities) ? result.capabilities : [],
            status: "active",
          }
          try {
            await fetch("/api/agents", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            })
          } finally {
            await mutate()
            router.push("/agents")
          }
        }}
      />
    </AppShell>
  )
}
