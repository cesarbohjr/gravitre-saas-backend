"use client"

import { type ComponentType } from "react"
import { useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
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
  Database,
  Copy,
  Check,
  ArrowRight,
  Activity,
  ExternalLink,
  GitBranch
} from "lucide-react"
import { NucleoAgent, NucleoConnector, NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { environmentsApi } from "@/lib/api"
import { toast } from "sonner"

function parseReportedCount(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value.replace(/,/g, ""))
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function parseReportedText(value: unknown): string | null {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function sumReported(values: Array<number | null>): string {
  if (values.every((value) => value == null)) return "Not reported"
  return String(values.reduce<number>((total, value) => total + (value ?? 0), 0))
}

interface Environment {
  id: string
  name: string
  slug: string
  status: "active" | "inactive" | "degraded"
  isDefault: boolean
  health: number | null
  resources: {
    workflows: number | null
    agents: number | null
    connectors: number | null
    sources: number | null
  }
  apiUrl: string | null
  createdAt: string | null
  lastActivity: string | null
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
      const isDefault = Boolean(
        item.is_default ?? item.isDefault ?? (slug === "production" || slug === "default"),
      )
      const status: Environment["status"] =
        item.is_active === false || item.isActive === false ? "inactive" : "active"
      const resources = (item.resources as Record<string, unknown> | undefined) ?? {}
      return {
        id: String(item.id ?? ""),
        name: name.charAt(0).toUpperCase() + name.slice(1),
        slug,
        status,
        isDefault,
        health: parseReportedCount(item.health ?? item.health_score),
        resources: {
          workflows: parseReportedCount(item.workflows ?? resources.workflows),
          agents: parseReportedCount(item.agents ?? resources.agents),
          connectors: parseReportedCount(item.connectors ?? resources.connectors),
          sources: parseReportedCount(item.sources ?? resources.sources),
        },
        apiUrl: parseReportedText(item.api_url ?? item.apiUrl),
        createdAt: parseReportedText(item.created_at ?? item.createdAt),
        lastActivity: parseReportedText(item.last_activity ?? item.lastActivity),
      } satisfies Environment
    })
    .filter((item) => item.id.length > 0)
  return normalized
}

// Health ring component
function HealthRing({ health, size = 48 }: { health: number | null; size?: number }) {
  const radius = (size - 6) / 2
  const circumference = 2 * Math.PI * radius
  const offset = health == null ? circumference : circumference - (health / 100) * circumference
  
  const color = health == null ? "stroke-muted-foreground" : health >= 90 ? "stroke-[color:var(--g-emerald)]" : health >= 70 ? "stroke-warning" : "stroke-destructive"
  
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
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
        {health == null ? "—" : `${health}%`}
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
  icon: ComponentType<{ className?: string }>
  count: number | null
  label: string
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary/50">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <div>
        <span className="text-sm font-semibold text-foreground">{count == null ? "Not reported" : count}</span>
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
    if (!environment.apiUrl) return
    navigator.clipboard.writeText(environment.apiUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const statusConfig = {
    active: { color: "border-[color:var(--g-emerald)]/50", bg: "bg-[color:var(--g-emerald-pale)]" },
    inactive: { color: "border-muted-foreground/50", bg: "bg-muted-foreground/5" },
    degraded: { color: "border-warning/50", bg: "bg-warning/5" },
  }
  const cfg = statusConfig[environment.status]

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "relative cursor-pointer rounded-[var(--np-radius-lg)] border-2 transition-all",
        cfg.color, cfg.bg,
        "bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)]",
        isSelected ? "ring-2 ring-[color:var(--g-emerald)]" : "hover:border-[color:var(--g-emerald)]/40"
      )}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="border-b border-divide p-5">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className={cn(
              "flex h-14 w-14 items-center justify-center rounded-xl",
              environment.name === "Production" 
                ? "bg-success/20" 
                : environment.name === "Staging"
                  ? "bg-info/20"
                  : "bg-warning/20"
            )}>
              <Server className={cn(
                "h-7 w-7",
                environment.name === "Production" 
                  ? "text-success" 
                  : environment.name === "Staging"
                    ? "text-info"
                    : "text-warning"
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
            {environment.lastActivity ?? "Not reported"}
          </span>
        </div>
      </div>

      {/* Resources */}
      <div className="border-b border-divide p-5">
        <div className="grid grid-cols-2 gap-2">
          <ResourceIndicator icon={NucleoWorkflow} count={environment.resources.workflows} label="workflows" />
          <ResourceIndicator icon={NucleoAgent} count={environment.resources.agents} label="agents" />
          <ResourceIndicator icon={NucleoConnector} count={environment.resources.connectors} label="connectors" />
          <ResourceIndicator icon={Database} count={environment.resources.sources} label="sources" />
        </div>
      </div>

      {/* API Endpoint */}
      <div className="p-5">
        <p className="text-xs text-muted-foreground mb-2 font-medium">API Endpoint</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs font-mono text-muted-foreground bg-secondary rounded-lg px-3 py-2 truncate">
            {environment.apiUrl ?? "Not reported"}
          </code>
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-8 w-8 shrink-0"
            onClick={handleCopyUrl}
            disabled={!environment.apiUrl}
            aria-label={copied ? "API endpoint copied" : "Copy API endpoint"}
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
            <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`${environment.name} environment options`}>
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
              Manage access
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2">
              <ExternalLink className="h-3.5 w-3.5" />
              Open dashboard
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
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
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
    if (!isAdmin) {
      toast.error("Admin role required to create environments")
      return
    }
    try {
      await environmentsApi.create({ name })
      toast.success("Environment created")
      await mutate()
    } catch (err) {
      console.error("[v0] Create failed:", err)
      const message = err instanceof Error ? err.message : "Failed to create environment"
      toast.error(message || "Failed to create environment")
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
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]" data-composition="manage">
        <GravitrePageHeader
          eyebrow="Infrastructure"
          title="Environments"
          description="Infrastructure overview and deployment pipeline"
          icon={<Server className="h-5 w-5" />}
          actions={
            <Button
              size="sm"
              className="h-8 gap-2"
              onClick={() => {
                if (!isAdmin) {
                  toast.error("Admin role required to create environments")
                  return
                }
                const existing = new Set(environments.map((env) => env.slug || env.name.toLowerCase()))
                const next =
                  ["production", "staging", "development"].find((name) => !existing.has(name)) ?? null
                if (!next) {
                  toast.error("All standard environments already exist")
                  return
                }
                void handleCreate(next)
              }}
              disabled={isLoading || adminLoading || !isAdmin}
            >
              <Plus className="h-3.5 w-3.5" />
              New environment
            </Button>
          }
        >
          {error && (
            <div className="mb-3 rounded-[var(--np-radius-md)] border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              Failed to load environments. Showing latest available data.
            </div>
          )}
        </GravitrePageHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-[var(--np-kpi-gap)] overflow-auto px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-6">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
            <GravitreMetric
              label="Active"
              value={isLoading ? "—" : environments.filter((e) => e.status === "active").length}
              hint="Environments online"
              icon={<Activity className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Total workflows"
              value={
                isLoading
                  ? "—"
                  : sumReported(environments.map((item) => item.resources.workflows))
              }
              hint="Across environments"
              icon={<NucleoWorkflow className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Total agents"
              value={
                isLoading ? "—" : sumReported(environments.map((item) => item.resources.agents))
              }
              hint="Across environments"
              icon={<NucleoAgent className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Environments"
              value={isLoading ? "—" : environments.length}
              hint="Configured"
              icon={<Server className="h-4 w-4" />}
            />
          </section>

          {!adminLoading && !isAdmin ? (
            <GravitreSurface className="p-3" padded={false}>
              <div className="flex items-center gap-3">
                <Shield className="h-4 w-4 text-warning" />
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Admin access required.</span>
                  {" "}Ask an organization owner to grant you admin before changing environments.
                </p>
              </div>
            </GravitreSurface>
          ) : (
            <GravitreSurface className="p-3" padded={false}>
              <div className="flex items-center gap-3">
                <Shield className="h-4 w-4 text-muted-foreground" />
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Organization-wide changes.</span>
                  {" "}Environment updates apply to every user in this workspace.
                </p>
              </div>
            </GravitreSurface>
          )}

          {/* Topology View */}
          <div className="mx-auto w-full max-w-5xl">
            {!isLoading && sortedEnvs.length === 0 ? (
              <GravitreEmpty
                icon={<Server className="h-5 w-5" />}
                title="No environments yet"
                hint="Create production to start your deployment pipeline."
                action={
                  <Button
                    size="sm"
                    className="gap-2"
                    disabled={!isAdmin || adminLoading}
                    onClick={() => void handleCreate("production")}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Create production
                  </Button>
                }
              />
            ) : (
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
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
