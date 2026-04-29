"use client"

import { useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { 
  Plus, 
  MoreHorizontal, 
  Settings, 
  Trash2, 
  Server,
  Shield,
  Users,
  Workflow,
  Database,
  Plug,
  Bot,
  Copy,
  Check,
  ArrowRight,
  Activity,
  Zap,
  ExternalLink,
  GitBranch
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { environmentsApi } from "@/lib/api"
import { toast } from "sonner"

interface Environment {
  id: string
  name: string
  slug: string
  status: "active" | "inactive" | "degraded"
  isDefault: boolean
  health: number
  resources: {
    workflows: number
    agents: number
    connectors: number
    sources: number
  }
  apiUrl: string
  createdAt: string
  lastActivity: string
  promotesTo?: string
  receivesFrom?: string
}

function normalizeEnvironmentsResponse(payload: unknown): Environment[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw = Array.isArray(model.environments) ? model.environments : null
  if (!raw) return []
  const normalized = raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => {
      const name = String(item.name ?? "Environment")
      const slug = name.trim().toLowerCase().replace(/\s+/g, "-")
      const isDefault = Boolean(item.is_default ?? item.isDefault ?? false)
      const status: Environment["status"] = "active"
      return {
        id: String(item.id ?? ""),
        name,
        slug,
        status,
        isDefault,
        health: 100,
        resources: {
          workflows: 0,
          agents: 0,
          connectors: 0,
          sources: 0,
        },
        apiUrl: `${window.location.origin}/api`,
        createdAt: "Recently created",
        lastActivity: "Just now",
      } satisfies Environment
    })
    .filter((item) => item.id.length > 0)
  return normalized
}

// Health ring component
function HealthRing({ health, size = 48 }: { health: number; size?: number }) {
  const radius = (size - 6) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (health / 100) * circumference
  
  const color = health >= 90 ? "stroke-emerald-500" : health >= 70 ? "stroke-amber-500" : "stroke-red-500"
  const glow = health >= 90 
    ? "drop-shadow-[0_0_8px_rgba(16,185,129,0.4)]" 
    : health >= 70 
      ? "drop-shadow-[0_0_8px_rgba(245,158,11,0.4)]"
      : "drop-shadow-[0_0_8px_rgba(239,68,68,0.4)]"
  
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className={cn("transform -rotate-90", glow)} width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={4}
          fill="none"
          className="stroke-secondary"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={4}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn("transition-all duration-700", color)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-xs font-semibold text-foreground">
        {health}%
      </span>
    </div>
  )
}

// Resource indicator
function ResourceIndicator({ 
  icon: Icon, 
  count, 
  label 
}: { 
  icon: typeof Workflow
  count: number
  label: string
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary/50">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <div>
        <span className="text-sm font-semibold text-foreground">{count}</span>
        <span className="text-xs text-muted-foreground ml-1">{label}</span>
      </div>
    </div>
  )
}

// Environment node in topology
function EnvironmentNode({ 
  environment,
  isSelected,
  onSelect,
  onDelete,
  isDeleting,
}: { 
  environment: Environment
  isSelected: boolean
  onSelect: () => void
  onDelete: (envId: string) => Promise<void>
  isDeleting: boolean
}) {
  const [copied, setCopied] = useState(false)

  const handleCopyUrl = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(environment.apiUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const statusConfig = {
    active: { color: "border-emerald-500/50", bg: "bg-emerald-500/5", glow: "shadow-[0_0_20px_rgba(16,185,129,0.15)]" },
    inactive: { color: "border-zinc-500/50", bg: "bg-zinc-500/5", glow: "" },
    degraded: { color: "border-amber-500/50", bg: "bg-amber-500/5", glow: "shadow-[0_0_20px_rgba(245,158,11,0.15)]" },
  }
  const cfg = statusConfig[environment.status]

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "relative rounded-2xl border-2 transition-all cursor-pointer",
        cfg.color, cfg.bg,
        isSelected ? `ring-2 ring-primary ${cfg.glow}` : "hover:border-primary/30"
      )}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="p-5 border-b border-border/50">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className={cn(
              "flex h-14 w-14 items-center justify-center rounded-xl",
              environment.name === "Production" 
                ? "bg-emerald-500/20" 
                : environment.name === "Staging"
                  ? "bg-blue-500/20"
                  : "bg-amber-500/20"
            )}>
              <Server className={cn(
                "h-7 w-7",
                environment.name === "Production" 
                  ? "text-emerald-400" 
                  : environment.name === "Staging"
                    ? "text-blue-400"
                    : "text-amber-400"
              )} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-foreground">{environment.name}</h3>
                {environment.isDefault && (
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                    Default
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground">{environment.slug}</p>
            </div>
          </div>
          <HealthRing health={environment.health} />
        </div>

        {/* Status & Activity */}
        <div className="flex items-center gap-3">
          <StatusBadge variant={environment.status === "active" ? "success" : environment.status === "degraded" ? "warning" : "muted"} dot>
            {environment.status}
          </StatusBadge>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Activity className="h-3 w-3" />
            {environment.lastActivity}
          </span>
        </div>
      </div>

      {/* Resources */}
      <div className="p-5 border-b border-border/50">
        <div className="grid grid-cols-2 gap-2">
          <ResourceIndicator icon={Workflow} count={environment.resources.workflows} label="workflows" />
          <ResourceIndicator icon={Bot} count={environment.resources.agents} label="agents" />
          <ResourceIndicator icon={Plug} count={environment.resources.connectors} label="connectors" />
          <ResourceIndicator icon={Database} count={environment.resources.sources} label="sources" />
        </div>
      </div>

      {/* API Endpoint */}
      <div className="p-5">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-2">API Endpoint</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs font-mono text-muted-foreground bg-secondary rounded-lg px-3 py-2 truncate">
            {environment.apiUrl}
          </code>
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-8 w-8 shrink-0"
            onClick={handleCopyUrl}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-success" />
            ) : (
              <Copy className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </Button>
        </div>
      </div>

      {/* Actions */}
      <div className="absolute top-4 right-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuItem className="gap-2">
              <Settings className="h-3.5 w-3.5" />
              Configure
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2">
              <Shield className="h-3.5 w-3.5" />
              Manage Access
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2">
              <ExternalLink className="h-3.5 w-3.5" />
              Open Dashboard
            </DropdownMenuItem>
            {!environment.isDefault && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="gap-2 text-destructive focus:text-destructive"
                  onClick={() => void onDelete(environment.id)}
                  disabled={isDeleting}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {isDeleting ? "Deleting..." : "Delete"}
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </motion.div>
  )
}

// Connection line between environments
function ConnectionLine({ from, to, label }: { from: string; to: string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-4">
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary border border-border">
        <GitBranch className="h-3 w-3 text-muted-foreground" />
        <span className="text-[10px] font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="h-8 w-px bg-gradient-to-b from-border via-primary/30 to-border" />
      <ArrowRight className="h-4 w-4 text-primary rotate-90" />
    </div>
  )
}

export default function EnvironmentsPage() {
  const { user } = useAuth()
  const [selectedEnv, setSelectedEnv] = useState<string | null>(null)
  const [mutatingEnvId, setMutatingEnvId] = useState<string | null>(null)
  const { data, error, isLoading, mutate } = useSWR(
    user ? "/api/environments" : null,
    apiFetcher,
    {
      fallbackData: { environments: [] as Environment[] },
      revalidateOnFocus: false,
      onError: (err) => console.error("[v0] Environments fetch error:", err),
    }
  )
  const environments = normalizeEnvironmentsResponse(data)

  const handleCreate = async (name: string) => {
    try {
      await environmentsApi.create({ name })
      toast.success("Environment created")
      await mutate()
    } catch (err) {
      console.error("[v0] Create failed:", err)
      toast.error("Failed to create environment")
    }
  }

  const handleDelete = async (envId: string) => {
    if (!window.confirm("Delete this environment? This cannot be undone.")) return
    try {
      setMutatingEnvId(envId)
      await environmentsApi.delete(envId)
      toast.success("Environment deleted")
      await mutate()
      if (selectedEnv === envId) {
        setSelectedEnv(null)
      }
    } catch (err) {
      console.error("[v0] Delete failed:", err)
      toast.error("Failed to delete environment")
    } finally {
      setMutatingEnvId((current) => (current === envId ? null : current))
    }
  }

  // Sort environments: development -> staging -> production
  const sortedEnvs = [...environments].sort((a, b) => {
    const order = { development: 0, staging: 1, production: 2 }
    return (order[a.slug as keyof typeof order] ?? 0) - (order[b.slug as keyof typeof order] ?? 0)
  })

  return (
    <AppShell title="Environments">
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-border">
          {error && (
            <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              Failed to load environments. Showing latest available data.
            </div>
          )}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-xl font-semibold text-foreground">System Topology</h1>
              <p className="text-sm text-muted-foreground mt-1">Infrastructure overview and deployment pipeline</p>
            </div>
            <Button
              size="sm"
              className="h-8 gap-2"
              onClick={() => {
                const name = window.prompt("Environment name")
                if (!name?.trim()) return
                void handleCreate(name.trim())
              }}
              disabled={isLoading}
            >
              <Plus className="h-3.5 w-3.5" />
              New Environment
            </Button>
          </div>

          {/* Quick stats */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-medium text-emerald-400">
                {environments.filter(e => e.status === "active").length} active
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <Workflow className="h-3 w-3 text-blue-400" />
              <span className="text-xs font-medium text-blue-400">
                {environments.reduce((a, e) => a + e.resources.workflows, 0)} total workflows
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-violet-500/10 border border-violet-500/20">
              <Bot className="h-3 w-3 text-violet-400" />
              <span className="text-xs font-medium text-violet-400">
                {environments.reduce((a, e) => a + e.resources.agents, 0)} total agents
              </span>
            </div>
          </div>
        </div>

        {/* Admin notice */}
        <div className="mx-6 mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
          <div className="flex items-center gap-3">
            <Shield className="h-4 w-4 text-amber-400" />
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Admin Access Required.</span>
              {" "}Changes here affect all users in the organization.
            </p>
          </div>
        </div>

        {/* Topology View */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-5xl mx-auto">
            {/* Pipeline visualization */}
            <div className="flex flex-col items-center">
              {sortedEnvs.map((env, index) => (
                <div key={env.id} className="w-full max-w-xl">
                  <EnvironmentNode
                    environment={env}
                    isSelected={selectedEnv === env.id}
                    onSelect={() => setSelectedEnv(selectedEnv === env.id ? null : env.id)}
                    onDelete={handleDelete}
                    isDeleting={mutatingEnvId === env.id}
                  />
                  {index < sortedEnvs.length - 1 && (
                    <ConnectionLine 
                      from={env.slug} 
                      to={sortedEnvs[index + 1].slug}
                      label={`Promotes to ${sortedEnvs[index + 1].name}`}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
