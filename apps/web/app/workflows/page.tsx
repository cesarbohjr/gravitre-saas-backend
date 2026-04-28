"use client"

import { useState } from "react"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatsGrid, StatCard } from "@/components/gravitre/page-header"
import { WorkflowCard, WorkflowGrid } from "@/components/gravitre/workflow-card"
import { DataTable } from "@/components/gravitre/data-table"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { 
  DataStream, 
  MorphingBackground, 
  GlowOrb, 
  AnimatedCounter,
  StatusBeacon,
  GridPattern
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { Icon } from "@/lib/icons"
import { Blocks, Edit, Workflow, Activity, Zap, Clock, TrendingUp } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
import { Target } from "lucide-react"
import { apiFetch, fetcher as apiFetcher } from "@/lib/fetcher"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"
import { workflowsApi } from "@/lib/api"
import type { Workflow as ApiWorkflow, WorkflowStatus } from "@/types/api"

interface WorkflowNode {
  id: string
  type: "source" | "agent" | "task" | "connector" | "approval"
  name: string
  status?: "success" | "running" | "failed" | "pending"
}

interface Workflow {
  id: string
  name: string
  description: string
  status: "active" | "paused" | "draft" | "error"
  environment: "production" | "staging"
  lastRun: string
  successRate: string
  runCount: number
  nodes?: WorkflowNode[]
  isRunning?: boolean
}

function normalizeWorkflow(input: Record<string, unknown>): Workflow {
  const status = String(input.status ?? "draft")
  const environment = String(input.environment ?? "staging")
  return {
    id: String(input.id ?? ""),
    name: String(input.name ?? "workflow"),
    description: String(input.description ?? ""),
    status:
      status === "active" || status === "paused" || status === "error"
        ? status
        : "draft",
    environment: environment === "production" ? "production" : "staging",
    lastRun: String(input.lastRun ?? input.last_run ?? "Never"),
    successRate: String(input.successRate ?? input.success_rate ?? "-"),
    runCount: Number(input.runCount ?? input.run_count ?? 0),
    nodes: Array.isArray(input.nodes) ? (input.nodes as WorkflowNode[]) : undefined,
    isRunning: Boolean(input.isRunning ?? input.is_running ?? false),
  }
}

function normalizeWorkflowsResponse(payload: unknown): Workflow[] {
  if (!payload || typeof payload !== "object") return fallbackWorkflows
  const model = payload as Record<string, unknown>
  const raw =
    (Array.isArray(model.workflows) ? model.workflows : null) ??
    (Array.isArray(model.data) ? model.data : null) ??
    (Array.isArray(model.items) ? model.items : null)
  if (!raw) return fallbackWorkflows
  const normalized = raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => normalizeWorkflow(item))
    .filter((item) => item.id.length > 0)
  return normalized.length > 0 ? normalized : fallbackWorkflows
}

// Fallback mock data with workflow nodes
const fallbackWorkflows: Workflow[] = [
  {
    id: "1",
    name: "sync-customers",
    description: "Synchronize customer data from Salesforce",
    status: "active",
    environment: "production",
    lastRun: "2 minutes ago",
    successRate: "98.5%",
    runCount: 1247,
    isRunning: true,
    nodes: [
      { id: "n1", type: "source", name: "Salesforce", status: "success" },
      { id: "n2", type: "agent", name: "Validator", status: "success" },
      { id: "n3", type: "task", name: "Transform", status: "running" },
      { id: "n4", type: "connector", name: "PostgreSQL", status: "pending" },
    ],
  },
  {
    id: "2",
    name: "etl-main-pipeline",
    description: "Main ETL pipeline for data warehouse",
    status: "active",
    environment: "production",
    lastRun: "5 minutes ago",
    successRate: "99.2%",
    runCount: 856,
    nodes: [
      { id: "n1", type: "source", name: "S3 Bucket", status: "success" },
      { id: "n2", type: "task", name: "Parse CSV", status: "success" },
      { id: "n3", type: "agent", name: "Enricher", status: "success" },
      { id: "n4", type: "approval", name: "QA Check", status: "success" },
      { id: "n5", type: "connector", name: "Snowflake", status: "success" },
    ],
  },
  {
    id: "3",
    name: "invoice-processing",
    description: "Process and validate incoming invoices",
    status: "paused",
    environment: "staging",
    lastRun: "1 hour ago",
    successRate: "94.1%",
    runCount: 432,
    nodes: [
      { id: "n1", type: "source", name: "Email", status: "success" },
      { id: "n2", type: "agent", name: "OCR Agent", status: "success" },
      { id: "n3", type: "task", name: "Validate", status: "success" },
      { id: "n4", type: "connector", name: "QuickBooks" },
    ],
  },
  {
    id: "4",
    name: "user-onboarding",
    description: "Handle new user registration workflow",
    status: "active",
    environment: "production",
    lastRun: "15 minutes ago",
    successRate: "99.8%",
    runCount: 2103,
    nodes: [
      { id: "n1", type: "source", name: "API Webhook", status: "success" },
      { id: "n2", type: "agent", name: "Profile Builder", status: "success" },
      { id: "n3", type: "connector", name: "SendGrid", status: "success" },
    ],
  },
  {
    id: "5",
    name: "data-cleanup",
    description: "Scheduled data cleanup and archival",
    status: "draft",
    environment: "staging",
    lastRun: "Never",
    successRate: "-",
    runCount: 0,
    nodes: [
      { id: "n1", type: "source", name: "Database" },
      { id: "n2", type: "task", name: "Filter Old" },
      { id: "n3", type: "connector", name: "Archive" },
    ],
  },
  {
    id: "6",
    name: "report-generation",
    description: "Generate and distribute weekly reports",
    status: "active",
    environment: "production",
    lastRun: "3 hours ago",
    successRate: "100%",
    runCount: 52,
    nodes: [
      { id: "n1", type: "source", name: "Analytics", status: "success" },
      { id: "n2", type: "agent", name: "Report Writer", status: "success" },
      { id: "n3", type: "connector", name: "Slack", status: "success" },
    ],
  },
]

const statusVariants: Record<string, "success" | "warning" | "muted"> = {
  active: "success",
  paused: "warning",
  draft: "muted",
}

const columns = [
  {
    key: "name",
    header: "Workflow",
    render: (item: Workflow) => (
      <div>
        <span className="font-medium text-foreground">{item.name}</span>
        <p className="text-xs text-muted-foreground mt-0.5">{item.description}</p>
      </div>
    ),
  },
  {
    key: "status",
    header: "Status",
    className: "w-28",
    render: (item: Workflow) => (
      <StatusBadge variant={statusVariants[item.status]} dot>
        {item.status}
      </StatusBadge>
    ),
  },
  {
    key: "environment",
    header: "Environment",
    className: "w-32",
    render: (item: Workflow) => (
      <EnvironmentBadge environment={item.environment} />
    ),
  },
  {
    key: "lastRun",
    header: "Last Run",
    className: "w-32",
    render: (item: Workflow) => (
      <span className="text-muted-foreground">{item.lastRun}</span>
    ),
  },
  {
    key: "successRate",
    header: "Success Rate",
    className: "w-28 text-right",
    render: (item: Workflow) => (
      <span className="text-muted-foreground">{item.successRate}</span>
    ),
  },
  {
    key: "runCount",
    header: "Runs",
    className: "w-20 text-right",
    render: (item: Workflow) => (
      <span className="text-muted-foreground">{item.runCount.toLocaleString()}</span>
    ),
  },
  {
    key: "actions",
    header: "",
    className: "w-24 text-right",
    render: (item: Workflow) => (
      <Link href={`/workflows/${item.id}/builder`}>
        <Button variant="ghost" size="sm" className="h-7 gap-1.5 text-xs">
          <Edit className="h-3 w-3" />
          Edit
        </Button>
      </Link>
    ),
  },
]

export default function WorkflowsPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid")
  const [searchQuery, setSearchQuery] = useState("")
  const [mesonWizardOpen, setMesonWizardOpen] = useState(false)
  const [goalWizardOpen, setGoalWizardOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  const [envFilter, setEnvFilter] = useState<string[]>([])
  
  // Fetch workflows - only when user is authenticated
  const { data, error, isLoading, mutate } = useSWR(
    user ? "/api/workflows" : null, 
    apiFetcher, 
    {
      fallbackData: { workflows: fallbackWorkflows },
      revalidateOnFocus: false,
      onError: (err) => {
        console.error("[v0] Workflows fetch error:", err)
      }
    }
  )

  const workflows = normalizeWorkflowsResponse(data)
  const activeCount = workflows.filter((w) => w.status === "active").length
  const pausedCount = workflows.filter((w) => w.status === "paused").length
  const runningCount = workflows.filter((w) => w.isRunning).length

  const filteredWorkflows = workflows.filter(w => {
    const matchesSearch = w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter.length === 0 || statusFilter.includes(w.status)
    const matchesEnv = envFilter.length === 0 || envFilter.includes(w.environment)
    return matchesSearch && matchesStatus && matchesEnv
  })
  
  const activeFiltersCount = statusFilter.length + envFilter.length

  // Handler functions for workflow actions
  const handleEditWorkflow = (id: string) => {
    router.push(`/workflows/${id}/builder`)
  }

  const handleViewRuns = (id: string) => {
    router.push(`/runs?workflow=${id}`)
  }

  const handleDuplicateWorkflow = async (workflow: Workflow) => {
    try {
      const duplicated = await workflowsApi.create({
        name: `${workflow.name}-copy`,
        description: workflow.description,
        status: "draft",
      })
      await mutate()
      toast.success(`Workflow duplicated: ${duplicated.name}`)
      router.push(`/workflows/${duplicated.id}/builder`)
    } catch (err) {
      console.error("[v0] Failed to duplicate workflow:", err)
      toast.error("Failed to duplicate workflow")
    }
  }

  const handleDeleteWorkflow = async (id: string) => {
    if (!confirm("Are you sure you want to delete this workflow?")) return
    
    // Optimistic update
    const previousWorkflows = workflows
    mutate({ workflows: workflows.filter(w => w.id !== id) }, false)
    
    try {
      await workflowsApi.delete(id)
      toast.success("Workflow deleted")
    } catch (err) {
      console.error("[v0] Failed to delete workflow:", err)
      mutate({ workflows: previousWorkflows }, false)
      toast.error("Failed to delete workflow")
    }
  }

  const handleToggleStatus = async (workflow: Workflow) => {
    const newStatus = workflow.status === "active" ? "paused" : "active"
    const optimistic = workflows.map((w) =>
      w.id === workflow.id ? { ...w, status: newStatus } : w
    )
    mutate({ workflows: optimistic }, false)

    try {
      await workflowsApi.update(workflow.id, { status: newStatus as WorkflowStatus })
      await mutate()
      toast.success(`Workflow ${newStatus === "active" ? "activated" : "paused"}`)
    } catch (err) {
      console.error("[v0] Failed to toggle workflow status:", err)
      mutate({ workflows }, false)
      toast.error("Unable to update workflow status")
    }
  }

  return (
    <AppShell title="Workflows">
      <div className="relative flex flex-col h-full overflow-hidden">
        {/* Premium ambient background */}
        <div className="absolute inset-0 pointer-events-none z-0">
          <MorphingBackground colors={["blue", "cyan", "emerald"]} />
          <div className="absolute inset-0 bg-background/90 backdrop-blur-3xl" />
        </div>
        
        {/* Animated flow lines */}
        <div className="absolute inset-0 pointer-events-none z-0">
          <DataStream direction="horizontal" color="blue" speed={0.3} className="opacity-20" />
          <GridPattern size={60} color="blue" animated className="opacity-30" />
        </div>
        
        {/* Ambient orbs */}
        <div className="absolute top-1/4 right-10 pointer-events-none z-0">
          <GlowOrb size={250} color="violet" intensity={0.2} />
        </div>
        <div className="absolute bottom-1/4 left-10 pointer-events-none z-0">
          <GlowOrb size={200} color="blue" intensity={0.15} />
        </div>

        {/* Header */}
        <div className="relative z-10">
          <PageHeader
            title="Workflows"
            description="Manage and monitor your automated workflows"
            icon={Workflow}
            iconColor="from-blue-500/20 to-cyan-500/20"
            actions={
            <>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 gap-2">
                    <Icon name="filter" size="sm" />
                    <span className="hidden sm:inline">Filter</span>
                    {activeFiltersCount > 0 && (
                      <span className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-info text-[10px] font-medium text-info-foreground">
                        {activeFiltersCount}
                      </span>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuLabel>Status</DropdownMenuLabel>
                  <DropdownMenuCheckboxItem
                    checked={statusFilter.includes("active")}
                    onCheckedChange={(checked) => 
                      setStatusFilter(checked 
                        ? [...statusFilter, "active"] 
                        : statusFilter.filter(s => s !== "active")
                      )
                    }
                  >
                    Active
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={statusFilter.includes("paused")}
                    onCheckedChange={(checked) => 
                      setStatusFilter(checked 
                        ? [...statusFilter, "paused"] 
                        : statusFilter.filter(s => s !== "paused")
                      )
                    }
                  >
                    Paused
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={statusFilter.includes("draft")}
                    onCheckedChange={(checked) => 
                      setStatusFilter(checked 
                        ? [...statusFilter, "draft"] 
                        : statusFilter.filter(s => s !== "draft")
                      )
                    }
                  >
                    Draft
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel>Environment</DropdownMenuLabel>
                  <DropdownMenuCheckboxItem
                    checked={envFilter.includes("production")}
                    onCheckedChange={(checked) => 
                      setEnvFilter(checked 
                        ? [...envFilter, "production"] 
                        : envFilter.filter(e => e !== "production")
                      )
                    }
                  >
                    Production
                  </DropdownMenuCheckboxItem>
                  <DropdownMenuCheckboxItem
                    checked={envFilter.includes("staging")}
                    onCheckedChange={(checked) => 
                      setEnvFilter(checked 
                        ? [...envFilter, "staging"] 
                        : envFilter.filter(e => e !== "staging")
                      )
                    }
                  >
                    Staging
                  </DropdownMenuCheckboxItem>
                  {activeFiltersCount > 0 && (
                    <>
                      <DropdownMenuSeparator />
                      <button
                        onClick={() => {
                          setStatusFilter([])
                          setEnvFilter([])
                        }}
                        className="w-full px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground text-left"
                      >
                        Clear all filters
                      </button>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setGoalWizardOpen(true)}
                className="h-8 gap-2 border-emerald-500/30 bg-emerald-500/5 hover:bg-emerald-500/10 hover:border-emerald-500/50 transition-colors"
              >
                <Target className="h-3.5 w-3.5 text-emerald-400" />
                <span className="hidden sm:inline text-emerald-400">Create from Goal</span>
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setMesonWizardOpen(true)}
                className="h-8 gap-2 border-violet-500/30 bg-transparent hover:bg-violet-500/10 hover:border-violet-500/50 transition-colors"
              >
                <Blocks className="h-3.5 w-3.5 text-violet-400" />
                <span className="hidden sm:inline text-violet-400">Build with Meson</span>
              </Button>
              <Link href="/workflows/new/builder">
                <Button size="sm" className="h-8 gap-2">
                  <Icon name="add" size="sm" />
                  <span className="hidden sm:inline">New Workflow</span>
                </Button>
              </Link>
            </>
          }
        >
          <StatsGrid columns={4}>
            <StatCard label="Total" value={workflows.length} />
            <StatCard label="Active" value={activeCount} variant="success" />
            <StatCard label="Paused" value={pausedCount} variant="warning" />
            <StatCard label="Running" value={runningCount} variant="info" />
          </StatsGrid>
        </PageHeader>
        </div>

        {/* Live activity banner */}
        {runningCount > 0 && (
          <motion.div 
            className="relative z-10 mx-4 md:mx-6 mb-4 px-4 py-3 rounded-xl bg-gradient-to-r from-blue-500/10 via-cyan-500/10 to-blue-500/10 border border-blue-500/20 backdrop-blur-sm"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <StatusBeacon status="processing" size="md" />
                </div>
                <div>
                  <div className="text-sm font-medium text-foreground">
                    <AnimatedCounter value={runningCount} duration={0.5} /> workflow{runningCount > 1 ? 's' : ''} running
                  </div>
                  <div className="text-xs text-muted-foreground">Processing data in real-time</div>
                </div>
              </div>
              <div className="hidden sm:flex items-center gap-4">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Activity className="h-3.5 w-3.5 text-blue-400" />
                  <span><AnimatedCounter value={3247} duration={1.5} /> records/min</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5 text-cyan-400" />
                  <span>Avg 1.2s latency</span>
                </div>
              </div>
            </div>
            {/* Progress bar */}
            <div className="mt-3 h-1 rounded-full bg-blue-500/10 overflow-hidden">
              <motion.div 
                className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full"
                initial={{ width: "0%" }}
                animate={{ width: ["0%", "100%", "0%"] }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
              />
            </div>
          </motion.div>
        )}

        <div className="relative z-10 flex-1 overflow-y-auto p-4 md:p-6 scrollbar-on-hover">
          {/* Error banner */}
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <Icon name="error" size="sm" emphasis />
              Failed to load from API. Showing cached data.
            </div>
          )}

          {/* Search and View Toggle */}
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative flex-1 sm:max-w-xs md:max-w-sm">
              <div className="absolute left-3 top-1/2 -translate-y-1/2">
                <Icon name="search" size="sm" className="text-muted-foreground" />
              </div>
              <input
                type="text"
                placeholder="Search workflows..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-9 rounded-lg border border-border bg-secondary/50 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/50"
              />
            </div>
            
            <div className="flex items-center gap-1 p-1 rounded-lg bg-secondary/50 border border-border shrink-0">
              <button
                onClick={() => setViewMode("grid")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  viewMode === "grid" 
                    ? "bg-card text-foreground shadow-sm" 
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon name="grid" size="sm" />
                Grid
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  viewMode === "table" 
                    ? "bg-card text-foreground shadow-sm" 
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon name="rows" size="sm" />
                Table
              </button>
            </div>
          </div>

          {/* Content - Premium animated */}
          <AnimatePresence mode="wait">
            {viewMode === "grid" ? (
              <motion.div
                key="grid"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3, type: "spring", stiffness: 100 }}
              >
                <WorkflowGrid>
                  {filteredWorkflows.map((workflow, index) => (
                    <motion.div
                      key={workflow.id}
                      initial={{ opacity: 0, y: 20, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ delay: index * 0.05, type: "spring", stiffness: 100 }}
                    >
                      <WorkflowCard
                        {...workflow}
                        onClick={() => router.push(`/workflows/${workflow.id}`)}
                        onEdit={() => handleEditWorkflow(workflow.id)}
                        onViewRuns={() => handleViewRuns(workflow.id)}
                        onDuplicate={() => handleDuplicateWorkflow(workflow)}
                        onDelete={() => handleDeleteWorkflow(workflow.id)}
                        onToggleStatus={() => handleToggleStatus(workflow)}
                      />
                    </motion.div>
                  ))}
                </WorkflowGrid>
                
                {/* Summary footer */}
                <motion.div 
                  className="mt-8 flex items-center justify-center gap-8 py-4"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 }}
                >
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="h-8 w-8 rounded-full bg-emerald-500/10 flex items-center justify-center">
                      <TrendingUp className="h-4 w-4 text-emerald-400" />
                    </div>
                    <span><AnimatedCounter value={98} duration={1} />% overall success rate</span>
                  </div>
                  <div className="w-px h-6 bg-border" />
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="h-8 w-8 rounded-full bg-blue-500/10 flex items-center justify-center">
                      <Zap className="h-4 w-4 text-blue-400" />
                    </div>
                    <span><AnimatedCounter value={4690} duration={1.5} /> runs this week</span>
                  </div>
                </motion.div>
              </motion.div>
            ) : (
              <motion.div
                key="table"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="rounded-xl border border-border bg-card/50 backdrop-blur-sm overflow-hidden"
              >
                <DataTable
                  columns={columns}
                  data={filteredWorkflows}
                  onRowClick={(workflow) => router.push(`/workflows/${workflow.id}`)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Meson Wizard */}
        <MesonWizard 
          open={mesonWizardOpen} 
          onClose={() => setMesonWizardOpen(false)}
          onComplete={(result) => {
            console.log("Meson result:", result)
            router.push("/workflows")
          }}
        />

        {/* Goal Workflow Wizard */}
        <GoalWorkflowWizard
          open={goalWizardOpen}
          onOpenChange={setGoalWizardOpen}
          onBuildWorkflow={(plan) => {
            console.log("Goal plan:", plan)
            router.push("/workflows/new/builder")
          }}
        />
      </div>
    </AppShell>
  )
}
