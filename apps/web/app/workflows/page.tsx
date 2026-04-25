"use client"

import { useEffect, useState } from "react"
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
import Link from "next/link"
import { useRouter } from "next/navigation"
import { MesonWizard } from "@/components/gravitre/meson-wizard"
import { fetcher } from "@/lib/fetcher"
import { EmptyState } from "@/components/gravitre/empty-state"
import { toast } from "sonner"

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


function toRelativeTime(value: string | null | undefined) {
  if (!value) return "Never"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Never"
  const diffMinutes = Math.max(1, Math.floor((Date.now() - date.getTime()) / 60000))
  if (diffMinutes < 60) return `${diffMinutes} minutes ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours} hours ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays} days ago`
}

function mapWorkflowStatus(status: string | null | undefined): Workflow["status"] {
  if (!status) return "draft"
  if (status === "active" || status === "paused" || status === "draft" || status === "error") {
    return status
  }
  if (status === "failed") return "error"
  return "draft"
}

function mapWorkflows(items: Array<Record<string, unknown>> | undefined): Workflow[] {
  if (!items || items.length === 0) return []
  return items.map((workflow, index) => {
    const successRateRaw = workflow.successRate
    const successRate =
      typeof successRateRaw === "number"
        ? `${successRateRaw.toFixed(1)}%`
        : String(successRateRaw ?? "0%")
    return {
      id: String(workflow.id ?? `workflow-${index}`),
      name: String(workflow.name ?? "Workflow"),
      description: String(workflow.description ?? workflow.goal ?? "No description provided"),
      status: mapWorkflowStatus(String(workflow.status ?? "draft")),
      environment: workflow.environment === "staging" ? "staging" : "production",
      lastRun: toRelativeTime((workflow.lastRun as string | undefined) ?? (workflow.last_run_at as string | undefined)),
      successRate,
      runCount: Number(workflow.runCount ?? workflow.run_count ?? 0),
      isRunning: String(workflow.status ?? "").toLowerCase() === "running",
      nodes: Array.isArray(workflow.nodes) ? (workflow.nodes as WorkflowNode[]) : undefined,
    }
  })
}

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
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid")
  const [searchQuery, setSearchQuery] = useState("")
  const [mesonWizardOpen, setMesonWizardOpen] = useState(false)
  
  const { data, error, isLoading, mutate } = useSWR<{ workflows: Array<Record<string, unknown>> }>("/api/workflows", fetcher, {
    revalidateOnFocus: false,
  })
  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  const workflows = mapWorkflows(data?.workflows)
  const activeCount = workflows.filter((w) => w.status === "active").length
  const pausedCount = workflows.filter((w) => w.status === "paused").length
  const runningCount = workflows.filter((w) => w.isRunning).length

  const filteredWorkflows = workflows.filter(w => 
    w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    w.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Handler functions for workflow actions
  const handleEditWorkflow = (id: string) => {
    router.push(`/workflows/${id}/builder`)
  }

  const handleViewRuns = (id: string) => {
    router.push(`/runs?workflow=${id}`)
  }

  const handleDuplicateWorkflow = (workflow: Workflow) => {
    // TODO: Replace with backend endpoint
    void workflow
    mutate()
  }

  const handleDeleteWorkflow = (id: string) => {
    if (confirm("Are you sure you want to delete this workflow?")) {
      // TODO: Replace with backend endpoint
      void id
      mutate()
    }
  }

  const handleToggleStatus = (workflow: Workflow) => {
    const newStatus = workflow.status === "active" ? "paused" : "active"
    void fetch(`/api/workflows/${workflow.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    }).finally(() => {
      mutate()
    })
  }

  if (isLoading) {
    return (
      <AppShell title="Workflows">
        <div className="space-y-4 p-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="Workflows">
        <EmptyState
          icon={Activity}
          title="Error loading data"
          description="Failed to load data"
          variant="error"
        />
      </AppShell>
    )
  }

  if (!workflows.length) {
    return (
      <AppShell title="Workflows">
        <EmptyState
          icon={Workflow}
          title="No workflows yet"
          description="Create your first workflow to get started"
          action={{ label: "New Workflow", onClick: () => router.push("/workflows/new/builder") }}
        />
      </AppShell>
    )
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
          <GlowOrb size={250} color="cyan" intensity={0.2} />
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
              <Button variant="outline" size="sm" className="h-8 gap-2">
                <Icon name="filter" size="sm" />
                <span className="hidden sm:inline">Filter</span>
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setMesonWizardOpen(true)}
                className="h-8 gap-2 border-violet-500/30 hover:bg-violet-500/10 hover:border-violet-500/50"
              >
                <Blocks className="h-3.5 w-3.5 text-violet-400" />
                <span className="hidden sm:inline text-violet-400">Generate</span>
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
      </div>
    </AppShell>
  )
}
