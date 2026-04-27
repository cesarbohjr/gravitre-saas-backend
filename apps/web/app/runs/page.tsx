"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { 
  Search, 
  RefreshCw, 
  Play, 
  Clock, 
  XCircle, 
  CheckCircle2,
  ChevronRight,
  RotateCcw,
  Eye,
  Zap,
  Activity,
  ArrowRight,
  Sparkles
} from "lucide-react"

interface Run {
  id: string
  workflowName: string
  workflowId: string
  status: "running" | "completed" | "failed" | "pending" | "cancelled"
  approvalStatus: "approved" | "pending" | "rejected" | "not_required"
  environment: "production" | "staging"
  startedAt: string
  duration: string
  steps?: { name: string; status: "completed" | "running" | "pending" | "failed" }[]
}

function normalizeRun(input: Record<string, unknown>): Run {
  const status = String(input.status ?? "pending")
  const approvalStatus = String(input.approvalStatus ?? input.approval_status ?? "not_required")
  const environment = String(input.environment ?? "staging")
  return {
    id: String(input.id ?? ""),
    workflowName: String(input.workflowName ?? input.workflow_name ?? "workflow"),
    workflowId: String(input.workflowId ?? input.workflow_id ?? ""),
    status:
      status === "running" ||
      status === "completed" ||
      status === "failed" ||
      status === "cancelled"
        ? status
        : "pending",
    approvalStatus:
      approvalStatus === "approved" ||
      approvalStatus === "pending" ||
      approvalStatus === "rejected"
        ? approvalStatus
        : "not_required",
    environment: environment === "production" ? "production" : "staging",
    startedAt: String(input.startedAt ?? input.started_at ?? "recently"),
    duration: String(input.duration ?? "-"),
    steps: Array.isArray(input.steps)
      ? (input.steps as { name: string; status: "completed" | "running" | "pending" | "failed" }[])
      : undefined,
  }
}

function normalizeRunsResponse(payload: unknown): Run[] {
  if (!payload || typeof payload !== "object") return fallbackRuns
  const model = payload as Record<string, unknown>
  const raw =
    (Array.isArray(model.runs) ? model.runs : null) ??
    (Array.isArray(model.data) ? model.data : null) ??
    (Array.isArray(model.items) ? model.items : null)
  if (!raw) return fallbackRuns
  const normalized = raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => normalizeRun(item))
    .filter((item) => item.id.length > 0)
  return normalized.length > 0 ? normalized : fallbackRuns
}

const fallbackRuns: Run[] = [
  {
    id: "run-1234",
    workflowName: "sync-customers",
    workflowId: "wf-001",
    status: "failed",
    approvalStatus: "approved",
    environment: "production",
    startedAt: "2 minutes ago",
    duration: "3m 24s",
    steps: [
      { name: "Fetch data", status: "completed" },
      { name: "Transform", status: "completed" },
      { name: "Sync to DB", status: "failed" },
    ],
  },
  {
    id: "run-1233",
    workflowName: "etl-main-pipeline",
    workflowId: "wf-002",
    status: "running",
    approvalStatus: "not_required",
    environment: "production",
    startedAt: "5 minutes ago",
    duration: "5m 12s",
    steps: [
      { name: "Extract", status: "completed" },
      { name: "Transform", status: "running" },
      { name: "Load", status: "pending" },
      { name: "Validate", status: "pending" },
    ],
  },
  {
    id: "run-1232",
    workflowName: "invoice-processing",
    workflowId: "wf-003",
    status: "pending",
    approvalStatus: "pending",
    environment: "staging",
    startedAt: "15 minutes ago",
    duration: "-",
    steps: [
      { name: "Parse invoices", status: "pending" },
      { name: "Validate", status: "pending" },
      { name: "Process", status: "pending" },
    ],
  },
  {
    id: "run-1231",
    workflowName: "user-onboarding",
    workflowId: "wf-004",
    status: "completed",
    approvalStatus: "approved",
    environment: "production",
    startedAt: "30 minutes ago",
    duration: "45s",
    steps: [
      { name: "Create user", status: "completed" },
      { name: "Send email", status: "completed" },
      { name: "Setup workspace", status: "completed" },
    ],
  },
  {
    id: "run-1230",
    workflowName: "data-cleanup",
    workflowId: "wf-005",
    status: "pending",
    approvalStatus: "pending",
    environment: "staging",
    startedAt: "1 hour ago",
    duration: "-",
    steps: [
      { name: "Scan records", status: "pending" },
      { name: "Archive", status: "pending" },
      { name: "Delete", status: "pending" },
    ],
  },
  {
    id: "run-1229",
    workflowName: "sync-customers",
    workflowId: "wf-001",
    status: "completed",
    approvalStatus: "not_required",
    environment: "production",
    startedAt: "2 hours ago",
    duration: "4m 12s",
    steps: [
      { name: "Fetch data", status: "completed" },
      { name: "Transform", status: "completed" },
      { name: "Sync to DB", status: "completed" },
    ],
  },
  {
    id: "run-1228",
    workflowName: "report-generation",
    workflowId: "wf-006",
    status: "cancelled",
    approvalStatus: "rejected",
    environment: "staging",
    startedAt: "3 hours ago",
    duration: "1m 30s",
    steps: [
      { name: "Gather data", status: "completed" },
      { name: "Generate", status: "failed" },
    ],
  },
]

const statusConfig = {
  running: { color: "text-blue-400", bg: "bg-blue-500/20", glow: "shadow-[0_0_20px_rgba(59,130,246,0.3)]", icon: Activity },
  completed: { color: "text-emerald-400", bg: "bg-emerald-500/20", glow: "", icon: CheckCircle2 },
  failed: { color: "text-red-400", bg: "bg-red-500/20", glow: "shadow-[0_0_20px_rgba(239,68,68,0.3)]", icon: XCircle },
  pending: { color: "text-amber-400", bg: "bg-amber-500/20", glow: "", icon: Clock },
  cancelled: { color: "text-zinc-400", bg: "bg-zinc-500/20", glow: "", icon: XCircle },
}

// Summary stats helper
function getSummaryStats(runs: Run[]) {
  return {
    active: runs.filter(r => r.status === "running").length,
    needsApproval: runs.filter(r => r.approvalStatus === "pending").length,
    failed: runs.filter(r => r.status === "failed").length,
    completed: runs.filter(r => r.status === "completed").length,
  }
}

// Timeline Node Component
function TimelineNode({ 
  run, 
  isExpanded, 
  onToggle,
  isFirst 
}: { 
  run: Run
  isExpanded: boolean
  onToggle: () => void
  isFirst: boolean
}) {
  const config = statusConfig[run.status]
  const StatusIcon = config.icon

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="relative"
    >
      {/* Timeline connector */}
      <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-border via-border to-transparent" />
      
      {/* Node */}
      <div className={cn(
        "relative ml-0 pl-14 pr-4 py-3 group cursor-pointer transition-all duration-200",
        isExpanded && "bg-card/50 rounded-lg border border-border/50"
      )}>
        {/* Status indicator */}
        <div className={cn(
          "absolute left-3 top-4 h-6 w-6 rounded-full flex items-center justify-center z-10 transition-all",
          config.bg,
          run.status === "running" && "animate-pulse",
          run.status === "failed" && config.glow
        )}>
          <StatusIcon className={cn("h-3.5 w-3.5", config.color)} />
        </div>

        {/* Live indicator for running */}
        {run.status === "running" && (
          <div className="absolute left-3 top-4 h-6 w-6">
            <span className="absolute inset-0 rounded-full bg-blue-500/30 animate-ping" />
          </div>
        )}

        {/* Main content */}
        <div 
          className="flex items-start justify-between gap-4"
          onClick={onToggle}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-foreground truncate">
                {run.workflowName}
              </span>
              <EnvironmentBadge environment={run.environment} />
              {run.approvalStatus === "pending" && (
                <span className="flex items-center gap-1 text-[10px] font-medium text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
                  <Clock className="h-2.5 w-2.5" />
                  Awaiting
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="font-mono">{run.id}</span>
              <span>{run.startedAt}</span>
              {run.duration !== "-" && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {run.duration}
                </span>
              )}
            </div>
          </div>

          {/* Duration bar visualization */}
          <div className="hidden sm:flex items-center gap-3">
            {run.duration !== "-" && (
              <div className="w-24 h-1.5 bg-secondary rounded-full overflow-hidden">
                <motion.div 
                  className={cn("h-full rounded-full", config.bg.replace("/20", ""))}
                  initial={{ width: 0 }}
                  animate={{ width: run.status === "running" ? "60%" : "100%" }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            )}
            <ChevronRight className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              isExpanded && "rotate-90"
            )} />
          </div>
        </div>

        {/* Expanded details */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-4 pt-4 border-t border-border/50">
                {/* Step progress */}
                {run.steps && (
                  <div className="mb-4">
                    {(() => {
                      const steps = run.steps ?? []
                      return (
                        <>
                    <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      Execution Steps
                    </p>
                    <div className="flex items-center gap-1">
                      {steps.map((step, i) => (
                        <div key={i} className="flex-1 flex items-center">
                          <div className={cn(
                            "flex-1 h-1.5 rounded-full transition-all",
                            step.status === "completed" && "bg-emerald-500",
                            step.status === "running" && "bg-blue-500 animate-pulse",
                            step.status === "pending" && "bg-secondary",
                            step.status === "failed" && "bg-red-500"
                          )} />
                          {i < steps.length - 1 && (
                            <ArrowRight className="h-3 w-3 text-muted-foreground mx-0.5 shrink-0" />
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="flex justify-between mt-1">
                      {steps.map((step, i) => (
                        <span 
                          key={i} 
                          className={cn(
                            "text-[10px]",
                            step.status === "running" ? "text-blue-400" :
                            step.status === "completed" ? "text-emerald-400" :
                            step.status === "failed" ? "text-red-400" :
                            "text-muted-foreground"
                          )}
                        >
                          {step.name}
                        </span>
                      ))}
                    </div>
                        </>
                      )
                    })()}
                  </div>
                )}

                {/* Quick actions */}
                <div className="flex items-center gap-2">
                  <Link href={`/runs/${run.id}`}>
                    <Button variant="outline" size="sm" className="h-7 gap-1.5 text-xs">
                      <Eye className="h-3 w-3" />
                      Inspect
                    </Button>
                  </Link>
                  {run.status === "failed" && (
                    <Button variant="outline" size="sm" className="h-7 gap-1.5 text-xs text-amber-400 border-amber-500/30 hover:bg-amber-500/10">
                      <RotateCcw className="h-3 w-3" />
                      Retry
                    </Button>
                  )}
                  {run.approvalStatus === "pending" && (
                    <Button size="sm" className="h-7 gap-1.5 text-xs">
                      <Zap className="h-3 w-3" />
                      Approve
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

export default function RunsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [timeRange, setTimeRange] = useState<string>("24h")
  const [expandedRun, setExpandedRun] = useState<string | null>(null)

  const { data, isLoading, mutate } = useSWR("/api/runs", apiFetcher, {
    fallbackData: { runs: fallbackRuns },
    revalidateOnFocus: false,
  })

  const runs = normalizeRunsResponse(data)
  const summaryStats = getSummaryStats(runs)

  // Filter runs
  const filteredRuns = runs.filter((run) => {
    if (statusFilter !== "all" && run.status !== statusFilter) return false
    return true
  })

  return (
    <AppShell title="Runs">
      <div className="flex flex-col h-full">
        {/* Header - fixed */}
        <div className="flex-shrink-0 px-4 md:px-6 pt-4 md:pt-6 pb-4 border-b border-border bg-gradient-to-b from-background to-background/80">
          <div className="flex items-center justify-between mb-4 md:mb-6">
            <div>
              <h1 className="text-lg md:text-xl font-semibold text-foreground">Execution Timeline</h1>
              <p className="text-xs md:text-sm text-muted-foreground mt-1">Real-time workflow monitoring</p>
            </div>
            <Button 
              variant="outline" 
              size="sm" 
              className="h-8 gap-2"
              onClick={() => mutate()}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>

          {/* Live Stats Bar */}
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
            {/* Stats row */}
            <div className="flex flex-wrap items-center gap-2 md:gap-4">
              {/* Active indicator */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <div className="relative">
                  <div className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                  <div className="absolute inset-0 h-2.5 w-2.5 rounded-full bg-blue-500 animate-ping" />
                </div>
                <div>
                  <span className="text-sm md:text-lg font-semibold text-blue-400">{summaryStats.active}</span>
                  <span className="text-[10px] md:text-xs text-muted-foreground ml-1">running</span>
                </div>
              </div>

              {/* Awaiting approval */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <Clock className="h-3.5 w-3.5 text-amber-400" />
                <div>
                  <span className="text-sm md:text-lg font-semibold text-amber-400">{summaryStats.needsApproval}</span>
                  <span className="text-[10px] md:text-xs text-muted-foreground ml-1">awaiting</span>
                </div>
              </div>

              {/* Failed */}
              {summaryStats.failed > 0 && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
                  <XCircle className="h-3.5 w-3.5 text-red-400" />
                  <div>
                    <span className="text-sm md:text-lg font-semibold text-red-400">{summaryStats.failed}</span>
                    <span className="text-[10px] md:text-xs text-muted-foreground ml-1">failed</span>
                  </div>
                </div>
              )}

              {/* Completed */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <div>
                  <span className="text-sm md:text-lg font-semibold text-emerald-400">{summaryStats.completed}</span>
                  <span className="text-[10px] md:text-xs text-muted-foreground ml-1">done</span>
                </div>
              </div>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2 md:ml-auto">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="h-8 w-[110px] md:w-[130px] text-xs bg-secondary border-border">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="running">Running</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                </SelectContent>
              </Select>
              <Select value={timeRange} onValueChange={setTimeRange}>
                <SelectTrigger className="h-8 w-[90px] md:w-[110px] text-xs bg-secondary border-border">
                  <SelectValue placeholder="Time" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1h">Last hour</SelectItem>
                  <SelectItem value="24h">Last 24h</SelectItem>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* Timeline - scrollable */}
        <div className="flex-1 overflow-auto px-4 md:px-6 py-4 md:py-6">
          {/* AI insight banner */}
          {summaryStats.failed > 0 && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 flex items-center gap-3 px-4 py-3 rounded-lg bg-gradient-to-r from-red-500/10 via-red-500/5 to-transparent border border-red-500/20"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-500/20">
                <Sparkles className="h-4 w-4 text-red-400" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">AI detected {summaryStats.failed} failed run{summaryStats.failed > 1 ? "s" : ""}</p>
                <p className="text-xs text-muted-foreground">Connection timeout in sync-customers - retry recommended</p>
              </div>
              <Button size="sm" variant="outline" className="h-7 text-xs border-red-500/30 text-red-400 hover:bg-red-500/10">
                <RotateCcw className="h-3 w-3 mr-1.5" />
                Auto-retry
              </Button>
            </motion.div>
          )}

          {/* Timeline */}
          <div className="space-y-1">
            {filteredRuns.map((run, index) => (
              <TimelineNode
                key={run.id}
                run={run}
                isFirst={index === 0}
                isExpanded={expandedRun === run.id}
                onToggle={() => setExpandedRun(expandedRun === run.id ? null : run.id)}
              />
            ))}
          </div>

          {filteredRuns.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary mb-4">
                <Activity className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">No runs matching your filters</p>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
