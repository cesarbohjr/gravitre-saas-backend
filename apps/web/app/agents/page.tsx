"use client"

// Agents Page — AI Team (Agents 4.0 Phase 2: department-grouped TEAM view)
import { Suspense, useEffect, useMemo, useRef, useState } from "react"
import useSWR, { mutate as globalMutate } from "swr"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { StatusChip } from "@/components/gravitre/visual"
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
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
import { NucleoAgent, NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { 
  Plus, 
  Search,
  RefreshCw,
  Sparkles,
  Brain,
  MessageSquare,
  Database,
  Play,
  Pause,
  Settings,
  X,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  PanelRightClose,
  PanelRightOpen,
  Shield,
  BookOpen,
  Users,
  Activity,
  Zap,
  Bot,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"
import { AgentSurfaceSwitch } from "@/components/agents/agent-surface-switch"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { agentsApi } from "@/lib/api"
import { ConnectorsAtmosphere } from "@/components/gravitre/connectors-atmosphere"
import { FleetControls, FleetSummaryBar, GraphView, ListView, TeamView } from "@/components/agents/fleet-v4"
import { AgentFleetInspectorBody } from "@/components/agents/fleet-v4/agent-fleet-inspector"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import { mapFleetDepartmentToApi, toFleetAgent } from "@/lib/agent-identity-bridge"
import { buildFleetGraphModel } from "@/lib/agents-fleet-graph"
import { filterFleetAgents, sortFleetAgents, uniqueSorted } from "@/lib/agents-fleet-query"
import { isAgentsFleetView } from "@/lib/agents-fleet-prefs"
import { useAgentsFleetPrefs } from "@/hooks/use-agents-fleet-prefs"
import { agentSwarmApi } from "@/lib/api"
import type { Agent as ApiAgent, AgentSwarmRun } from "@/types/api"
import {
  agentStatusIsLiveWork,
  normalizeAgentStatus,
  presentAgentStatus,
  taskRuntimeBadgeClass,
  taskRuntimeLabel,
} from "@/lib/agent-runtime-status"
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
  connectedSystems?: string[]
  workflowCount?: number
  parentAgentId?: string | null
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
  const status = normalizeAgentStatus(input.status)
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
    status,
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
    stats: (() => {
      const tasksToday = Number(stats.tasksToday ?? stats.tasks_today ?? 0)
      const raw = stats.successRate ?? stats.success_rate
      const hasRate = raw !== undefined && raw !== null && raw !== ""
      const parsed = hasRate ? Number(raw) : NaN
      const successRate =
        !hasRate || !Number.isFinite(parsed) ? null : parsed
      return {
        tasksToday,
        successRate,
        successRateSource:
          (typeof stats.successRateSource === "string"
            ? stats.successRateSource
            : successRate == null
              ? "insufficient_data"
              : "stored_column") as Agent["stats"]["successRateSource"],
        avgResponseTime: String(stats.avgResponseTime ?? stats.avg_response_time ?? "-"),
        workflowsUsing: Number(
          stats.workflowsUsing ??
            stats.workflows_using ??
            input.workflowCount ??
            input.workflow_count ??
            0,
        ),
      }
    })(),
    capabilities: Array.isArray(input.capabilities)
      ? (input.capabilities as string[])
      : [],
    permissions: Array.isArray(input.permissions)
      ? (input.permissions as string[])
      : Array.isArray(input.systems)
      ? (input.systems as string[])
      : [],
    connectedSystems: Array.isArray(input.connectedSystems)
      ? (input.connectedSystems as string[]).map(String)
      : Array.isArray(input.connected_systems)
        ? (input.connected_systems as string[]).map(String)
        : Array.isArray(input.systems)
          ? (input.systems as string[]).map(String)
          : [],
    workflowCount: Number(input.workflowCount ?? input.workflow_count ?? stats.workflowsUsing ?? 0),
    parentAgentId:
      typeof input.parentAgentId === "string"
        ? input.parentAgentId
        : typeof input.parent_agent_id === "string"
          ? input.parent_agent_id
          : null,
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

const statusConfig = {
  active: presentAgentStatus("active"),
  idle: presentAgentStatus("idle"),
  processing: presentAgentStatus("processing"),
  error: presentAgentStatus("error"),
} as const

/** Phase 5 honesty: withhold rate when null / no tasks / idle-zero. */
function getDisplaySuccessRate(agent: Agent): number | null {
  const rate = agent.stats.successRate
  if (rate == null || Number.isNaN(Number(rate))) return null
  if (agent.stats.tasksToday <= 0) return null
  if (agent.status === "idle" && rate === 0) return null
  return rate
}

function shouldShowSuccessRate(agent: Agent): boolean {
  return getDisplaySuccessRate(agent) != null
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
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="flex h-full flex-col overflow-y-auto"
    >
      <AgentFleetInspectorBody
        agent={agent}
        layout="panel"
        onStart={(a) => onStart(a as Agent)}
        onStop={(a) => onStop(a as Agent)}
        isMutating={isMutating}
        successRateDisplay={getDisplaySuccessRate(agent)}
      />
    </motion.div>
  )
}

function AgentPreviewSheet({
  agent,
  open,
  onOpenChange,
}: {
  agent: Agent
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenProfile?: () => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto p-0 sm:max-w-sm">
        <SheetHeader className="sr-only">
          <SheetTitle>{agent.name}</SheetTitle>
          <SheetDescription>{agent.role}</SheetDescription>
        </SheetHeader>
        <AgentFleetInspectorBody
          agent={agent}
          layout="sheet"
          successRateDisplay={getDisplaySuccessRate(agent)}
        />
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
  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            onClick={onClick}
            aria-expanded={isOpen}
            aria-haspopup="dialog"
            aria-label="Build with Meson"
            className={cn(
              "gap-2 px-3 text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
              isOpen && "bg-[color:var(--g-surface-active)] text-[color:var(--g-text-primary)]",
            )}
          >
            <NucleoIntelligence className="h-4 w-4 text-[color:var(--g-intelligence)]" />
            <span className="hidden font-medium sm:inline">Build with Meson</span>
            <span className="text-sm font-medium sm:hidden">Meson</span>
          </Button>
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
  const { prefs, hydrated, setView, setSort, toggleSortDir, setFilters, clearFilters } =
    useAgentsFleetPrefs()

  const normalizedSearchQuery = searchQuery.trim().toLowerCase()

  // URL ?view=team|list|graph is shareable; applies once after prefs hydrate.
  useEffect(() => {
    if (!hydrated) return
    const param = new URLSearchParams(window.location.search).get("view")
    if (isAgentsFleetView(param) && param !== prefs.view) {
      setView(param)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot URL override after hydrate
  }, [hydrated])

  useEffect(() => {
    if (!hydrated || typeof window === "undefined") return
    const url = new URL(window.location.href)
    if (url.searchParams.get("view") === prefs.view) return
    url.searchParams.set("view", prefs.view)
    const qs = url.searchParams.toString()
    window.history.replaceState({}, "", `${url.pathname}${qs ? `?${qs}` : ""}${url.hash}`)
  }, [prefs.view, hydrated])

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

  const handleDepartmentChange = async (agentId: string, department: AgentDepartmentId) => {
    const agent = agents.find((a) => a.id === agentId)
    if (!agent) return
    const label = mapFleetDepartmentToApi(department)
    if (String(agent.department ?? "").trim().toLowerCase() === label.toLowerCase()) return
    try {
      setIsMutatingAgent(agentId)
      await agentsApi.update(agentId, { department: label as Agent["department"] })
      toast.success(`${agent.name} moved to ${label}`)
      await mutate()
      if (selectedAgent?.id === agentId) {
        setSelectedAgent({ ...selectedAgent, department: label as Agent["department"] })
      }
    } catch (err) {
      console.error("[v0] Failed to move agent department:", err)
      toast.error(`Failed to move ${agent.name}`)
    } finally {
      setIsMutatingAgent((current) => (current === agentId ? null : current))
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

  const activeCount = agents.filter((a) => a.status === "active").length
  const runningCount = agents.filter((a) => a.status === "processing").length
  const idleCount = agents.filter((a) => a.status === "idle").length
  const failedCount = agents.filter((a) => a.status === "error").length
  const totalTasks = agents.reduce((sum, a) => sum + a.stats.tasksToday, 0)
  const totalAgents = agents.length

  const hasActiveFilters = Boolean(
    prefs.filters.department ||
      prefs.filters.status ||
      prefs.filters.role ||
      prefs.filters.model,
  )

  const fleetAgents = useMemo(() => {
    const mapped = filteredAgents.map((agent) =>
      toFleetAgent({
        ...agent,
        connectedSystems: agent.connectedSystems,
        workflowCount: agent.workflowCount ?? agent.stats.workflowsUsing,
        parentAgentId: agent.parentAgentId,
      }),
    )
    const filtered = filterFleetAgents(mapped, prefs.filters)
    return sortFleetAgents(filtered, prefs.sort, prefs.sortDir)
  }, [filteredAgents, prefs.filters, prefs.sort, prefs.sortDir])

  const filterOptions = useMemo(() => {
    const mapped = agents.map((agent) =>
      toFleetAgent({
        ...agent,
        connectedSystems: agent.connectedSystems,
        workflowCount: agent.workflowCount ?? agent.stats.workflowsUsing,
        parentAgentId: agent.parentAgentId,
      }),
    )
    return {
      departments: uniqueSorted(mapped.map((a) => a.departmentLabel)),
      roles: uniqueSorted(mapped.map((a) => a.role)),
      models: uniqueSorted(mapped.map((a) => a.model).filter((m) => m && m !== "—")),
    }
  }, [agents])

  const agentsById = useMemo(() => {
    const map = new Map<string, Agent>()
    for (const agent of agents) map.set(agent.id, agent)
    return map
  }, [agents])

  // Fetch swarm runs when GRAPH is open — hydrate subtasks for active runs only.
  const { data: swarmList } = useSWR(
    user && prefs.view === "graph" ? "agents-fleet-swarm" : null,
    () => agentSwarmApi.list({ limit: 12 }),
    { revalidateOnFocus: true, dedupingInterval: 5000 },
  )

  const [swarmRunsDetailed, setSwarmRunsDetailed] = useState<AgentSwarmRun[]>([])

  useEffect(() => {
    if (prefs.view !== "graph") {
      setSwarmRunsDetailed([])
      return
    }
    const runs = swarmList?.runs ?? []
    const candidates = runs.filter((r) =>
      ["pending", "running", "aggregating"].includes(String(r.status)),
    )
    if (candidates.length === 0) {
      setSwarmRunsDetailed([])
      return
    }
    let cancelled = false
    void (async () => {
      const detailed = await Promise.all(
        candidates.slice(0, 3).map(async (run) => {
          try {
            return await agentSwarmApi.get(run.id)
          } catch {
            return run
          }
        }),
      )
      if (!cancelled) setSwarmRunsDetailed(detailed)
    })()
    return () => {
      cancelled = true
    }
  }, [prefs.view, swarmList])

  const graphModel = useMemo(
    () => buildFleetGraphModel(fleetAgents, swarmRunsDetailed),
    [fleetAgents, swarmRunsDetailed],
  )

  const selectAgentById = (id: string) => {
    const agent = agentsById.get(id)
    if (!agent) return
    setSelectedAgent(agent)
    setPreviewOpen(true)
  }

  const prevRunningCountRef = useRef(runningCount)
  const [runningStatPulse, setRunningStatPulse] = useState(false)

  useEffect(() => {
    if (prevRunningCountRef.current === runningCount) return
    prevRunningCountRef.current = runningCount
    setRunningStatPulse(true)
    const t = window.setTimeout(() => setRunningStatPulse(false), 700)
    return () => window.clearTimeout(t)
  }, [runningCount])

  const rosterActions = (
    <>
      <Button onClick={() => router.push("/agents/new")} className="gap-2">
        <Plus className="h-4 w-4" />
        <span className="hidden sm:inline">New Agent</span>
      </Button>
      <Button variant="outline" onClick={() => router.push(APP_ROUTES.multiAgentRun)} className="gap-2">
        <Users className="h-4 w-4" />
        <span className="hidden sm:inline">Multi-Agent Run</span>
      </Button>
      <MesonBuildButton
        onClick={() => setMesonWizardOpen(true)}
        isOpen={mesonWizardOpen}
      />
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
    <div className="relative flex h-full flex-col overflow-hidden bg-[color:var(--g-canvas)] lg:flex-row">
  {/* Left - Agent roster */}
  <div className="relative z-10 flex flex-1 flex-col border-divide lg:border-r">
          <div className="relative z-10 space-y-3 px-[var(--np-page-pad-sm)] pt-4 sm:px-[var(--np-page-pad)]">
            <Suspense fallback={null}>
              <AgentsHubTabs active="roster" />
            </Suspense>
            <AgentSurfaceSwitch surface="operate" />
          </div>
          {/* Collapse only hides overview title/stats — primary CTAs stay reachable. */}
          {!headerCollapsed ? (
            <>
              <GravitrePageHeader
                className="shrink-0"
                eyebrow="AI Team"
                title={SURFACE_COPY.pages.agents.rosterTitle}
                description={SURFACE_COPY.pages.agents.description}
                icon={<NucleoAgent className="h-5 w-5" />}
                actions={rosterActions}
              />
              <div className="px-[var(--np-page-pad-sm)] pb-3 sm:px-[var(--np-page-pad)]">
                <motion.div
                  animate={runningStatPulse ? { scale: [1, 1.01, 1] } : { scale: 1 }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                >
                  <FleetSummaryBar
                    counts={{
                      total: totalAgents,
                      working: runningCount,
                      available: activeCount,
                      idle: idleCount,
                      failed: failedCount,
                      tasksToday: totalTasks,
                    }}
                  />
                </motion.div>
              </div>
            </>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-divide bg-[color:var(--g-surface-1)]/60 px-[var(--np-page-pad-sm)] py-2.5 backdrop-blur-sm sm:px-[var(--np-page-pad)]">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold tracking-tight text-[color:var(--g-text-primary)]">
                  {SURFACE_COPY.pages.agents.rosterTitle}
                </p>
                <p className="text-xs text-[color:var(--g-text-muted)]">
                  {runningCount} working · {activeCount} available · {idleCount} idle · {totalAgents} total
                  {failedCount > 0 ? ` · ${failedCount} failed` : ""}
                  {totalTasks > 0 ? ` · ${totalTasks} tasks today` : ""}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">{rosterActions}</div>
            </div>
          )}

          {/* Search + view / filter / sort */}
          <div className="space-y-3 border-b border-divide px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--g-text-muted)]" />
                <input
                  ref={searchInputRef}
                  type="search"
                  placeholder="Search name, role, department, model, status…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search agents"
                  className="h-10 w-full rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] pl-9 pr-9 text-sm focus:outline-none focus:ring-1 focus:ring-ring sm:h-9"
                />
                {searchQuery ? (
                  <button
                    type="button"
                    aria-label="Clear search"
                    onClick={() => {
                      setSearchQuery("")
                      searchInputRef.current?.focus()
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[color:var(--g-text-muted)] transition-colors hover:bg-[color:var(--g-surface-active)] hover:text-[color:var(--g-text-primary)]"
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
            <FleetControls
              view={prefs.view}
              onViewChange={setView}
              sort={prefs.sort}
              sortDir={prefs.sortDir}
              onSortChange={setSort}
              onToggleSortDir={toggleSortDir}
              filters={prefs.filters}
              onFiltersChange={setFilters}
              onClearFilters={clearFilters}
              departments={filterOptions.departments}
              roles={filterOptions.roles}
              models={filterOptions.models}
            />
            {(normalizedSearchQuery ||
              prefs.filters.department ||
              prefs.filters.status ||
              prefs.filters.role ||
              prefs.filters.model) &&
            agents.length > 0 ? (
              <p className="text-xs text-[color:var(--g-text-muted)]">
                {fleetAgents.length} of {agents.length} agent{agents.length === 1 ? "" : "s"}
              </p>
            ) : null}
          </div>

          {/* TEAM / LIST / GRAPH — Nodus Connectors atmosphere + department DnD */}
          <div className="relative flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] sm:py-4">
            <ConnectorsAtmosphere className="z-0" />
            <div className="relative z-10 w-full min-h-[360px] flex-1 sm:min-h-0">
              {error ? (
                <WorkSectionErrorCard
                  title="Could not load agents"
                  message="We couldn't reach the agents service. Check your connection and try again."
                  onRetry={() => void mutate()}
                  className="mx-auto max-w-sm"
                />
              ) : isLoading && agents.length === 0 ? (
                prefs.view === "list" ? (
                  <div className="space-y-2 rounded-[var(--np-radius-lg)] border border-divide p-4">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <Skeleton key={index} className="h-10 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-6">
                    {Array.from({ length: 2 }).map((_, section) => (
                      <div key={section} className="space-y-3">
                        <Skeleton className="h-3 w-24" />
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                          {Array.from({ length: 3 }).map((_, index) => (
                            <div
                              key={index}
                              className="flex items-start gap-3 rounded-[var(--np-radius-md)] border border-divide p-3"
                            >
                              <Skeleton className="h-11 w-11 rounded-[var(--np-radius-md)]" />
                              <div className="flex-1 space-y-2">
                                <Skeleton className="h-3 w-32" />
                                <Skeleton className="h-2 w-24" />
                                <Skeleton className="h-5 w-16" />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              ) : fleetAgents.length === 0 ? (
                <div className="mx-auto w-full max-w-sm px-4">
                  {normalizedSearchQuery ||
                  prefs.filters.department ||
                  prefs.filters.status ||
                  prefs.filters.role ||
                  prefs.filters.model ? (
                    <GravitreEmpty
                      icon={<Bot className="h-5 w-5" />}
                      title="No agents match"
                      hint="Try clearing search or filters."
                      action={
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSearchQuery("")
                            clearFilters()
                            searchInputRef.current?.focus()
                          }}
                        >
                          Clear search & filters
                        </Button>
                      }
                    />
                  ) : (
                    <GravitreEmpty
                      icon={<Bot className="h-5 w-5" />}
                      title="No agents yet"
                      hint="Create your first AI teammate to start delegating work."
                      action={
                        <Button onClick={() => router.push("/agents/new")} className="gap-2">
                          <Plus className="h-4 w-4" />
                          New Agent
                        </Button>
                      }
                    />
                  )}
                </div>
              ) : prefs.view === "list" ? (
                <ListView
                  agents={fleetAgents}
                  selectedId={visibleSelectedAgent?.id ?? null}
                  onSelect={selectAgentById}
                  onDepartmentChange={handleDepartmentChange}
                  showEmptyDepartments={!hasActiveFilters}
                  toolbar={
                    <p className="text-xs text-[color:var(--g-text-muted)]">
                      {hasActiveFilters
                        ? "Filtered list — clear filters to drag agents between departments"
                        : "List view — drag rows onto a department to reassign"}
                    </p>
                  }
                />
              ) : prefs.view === "graph" ? (
                <div className="space-y-2">
                  {graphModel.hasLiveSwarm ? (
                    <p className="text-xs text-[color:var(--g-brand)]">
                      Live multi-agent swarm path highlighted
                    </p>
                  ) : (
                    <p className="text-xs text-[color:var(--g-text-muted)]">
                      Graph shows parent links, swarm delegation, and connector usage — only
                      edges backed by data
                      {hasActiveFilters
                        ? "."
                        : ". Drag agents onto a department to reassign."}
                    </p>
                  )}
                  <GraphView
                    agents={fleetAgents}
                    edges={graphModel.edges}
                    extraNodes={graphModel.extraNodes}
                    selectedId={visibleSelectedAgent?.id ?? null}
                    onSelect={selectAgentById}
                    onDepartmentChange={handleDepartmentChange}
                    showEmptyDepartments={!hasActiveFilters}
                    activeAgentIds={graphModel.activeAgentIds}
                  />
                </div>
              ) : (
                <TeamView
                  agents={fleetAgents}
                  selectedId={visibleSelectedAgent?.id ?? null}
                  grouped
                  onSelect={selectAgentById}
                  onDepartmentChange={handleDepartmentChange}
                  showEmptyDepartments={!hasActiveFilters}
                />
              )}
            </div>
          </div>
        </div>

        {visibleSelectedAgent ? (
          <AgentPreviewSheet
            agent={visibleSelectedAgent}
            open={previewOpen}
            onOpenChange={setPreviewOpen}
          />
        ) : null}

{/* Right - Agent Detail Panel */}
        <AnimatePresence initial={false}>
          {/* Only reserve the side-panel width when there is actually an agent
             to show. Previously the panel defaulted open and reserved 420px even
             with no selection, leaving a large empty panel that squeezed the roster.
             stage into a narrow strip. */}
          {detailPanelOpen && visibleSelectedAgent ? (
            <motion.div
              key="agent-detail-panel"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 420, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="relative z-10 hidden shrink-0 overflow-hidden border-t border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] lg:block lg:border-l lg:border-t-0"
            >
              {/* Was a full-opacity violet -> blue -> emerald rainbow strip,
                  which read as decoration rather than as part of the product.
                  A single brand-primary rule does the same job of capping the
                  panel without introducing three off-palette hues. */}
              <div className="absolute inset-x-0 top-0 h-1 bg-primary" />
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
