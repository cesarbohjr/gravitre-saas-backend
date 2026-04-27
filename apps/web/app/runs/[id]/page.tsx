"use client"

import { use, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { apiFetch, fetcher } from "@/lib/fetcher"
import {
  ArrowLeft,
  RefreshCw,
  XCircle,
  Clock,
  Database,
  CheckCircle,
  AlertCircle,
  Play,
  Pause,
  TerminalSquare,
  RotateCcw,
  AlertTriangle,
  Loader2,
} from "lucide-react"

interface Step {
  id: string
  name: string
  status: "completed" | "running" | "failed" | "pending" | "skipped"
  duration: string
  startedAt: string
  logs?: string[]
}

interface Run {
  id: string
  workflowId: string
  workflowName: string
  status: "running" | "completed" | "failed" | "pending"
  environment: "production" | "staging"
  triggeredBy: string
  duration: string
  recordsProcessed: number
  stepsCompleted: number
  stepsTotal: number
  errorMessage?: string
  startedAt: string
}

const fallbackRun: Run = {
  id: "run-sync-1234",
  workflowId: "wf-sync-customers",
  workflowName: "sync-customers",
  status: "failed",
  environment: "production",
  triggeredBy: "Schedule",
  duration: "3m 24s",
  recordsProcessed: 12450,
  stepsCompleted: 2,
  stepsTotal: 5,
  errorMessage: "Connection timeout",
  startedAt: "14:32:00 UTC",
}

const fallbackSteps: Step[] = [
  {
    id: "1",
    name: "Initialize",
    status: "completed",
    duration: "2s",
    startedAt: "14:32:00 UTC",
    logs: ["Initializing workflow context", "Loading configuration", "Ready to proceed"],
  },
  {
    id: "2",
    name: "Fetch Source Data",
    status: "completed",
    duration: "45s",
    startedAt: "14:32:02 UTC",
    logs: [
      "Connecting to Salesforce API",
      "Authenticated successfully",
      "Fetching customer records...",
      "Retrieved 12,450 records",
    ],
  },
  {
    id: "3",
    name: "Transform Data",
    status: "failed",
    duration: "2m 35s",
    startedAt: "14:32:47 UTC",
    logs: [
      "Starting data transformation",
      "Processing batch 1/25...",
      "Processing batch 2/25...",
      "ERROR: Connection timeout after 30000ms",
      "Transformation failed at record #5,234",
    ],
  },
  {
    id: "4",
    name: "Load to Destination",
    status: "skipped",
    duration: "-",
    startedAt: "-",
  },
  {
    id: "5",
    name: "Finalize",
    status: "skipped",
    duration: "-",
    startedAt: "-",
  },
]

const stepStatusIcons = {
  completed: CheckCircle,
  running: Play,
  failed: AlertCircle,
  pending: Clock,
  skipped: Pause,
}

const stepStatusColors = {
  completed: "text-success",
  running: "text-info",
  failed: "text-destructive",
  pending: "text-warning",
  skipped: "text-muted-foreground",
}

const statusVariants: Record<string, "success" | "error" | "warning" | "info"> = {
  completed: "success",
  failed: "error",
  running: "info",
  pending: "warning",
}

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const isAdmin = true

  const [showRollbackConfirm, setShowRollbackConfirm] = useState(false)
  const [isRollingBack, setIsRollingBack] = useState(false)
  const [rollbackError, setRollbackError] = useState<string | null>(null)
  const [isRetrying, setIsRetrying] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)

  const { data, error, isLoading, mutate } = useSWR<{ run: Run; steps: Step[] }>(
    `/api/runs/${id}`,
    fetcher,
    {
      fallbackData: { run: { ...fallbackRun, id }, steps: fallbackSteps },
      revalidateOnFocus: false,
    }
  )

  const run = data?.run ?? { ...fallbackRun, id }
  const steps = data?.steps ?? fallbackSteps

  const handleRetry = async () => {
    setIsRetrying(true)
    try {
      const response = await apiFetch(`/api/runs/${id}/retry`, { method: "POST" })
      if (response.ok) {
        mutate()
      }
    } catch {
      // Handle error silently
    } finally {
      setIsRetrying(false)
    }
  }

  const handleCancel = async () => {
    setIsCancelling(true)
    try {
      const response = await apiFetch(`/api/runs/${id}/cancel`, { method: "POST" })
      if (response.ok) {
        mutate()
      }
    } catch {
      // Handle error silently
    } finally {
      setIsCancelling(false)
    }
  }

  const handleRequestRollback = () => {
    setShowRollbackConfirm(true)
    setRollbackError(null)
  }

  const handleConfirmRollback = async () => {
    setIsRollingBack(true)
    setRollbackError(null)
    try {
      const response = await apiFetch(`/api/runs/${id}/rollback`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || "Rollback failed")
      }
      setShowRollbackConfirm(false)
      mutate()
    } catch (err) {
      setRollbackError(err instanceof Error ? err.message : "Failed to initiate rollback. Please try again.")
    } finally {
      setIsRollingBack(false)
    }
  }

  const handleCancelRollback = () => {
    setShowRollbackConfirm(false)
    setRollbackError(null)
  }

  if (isLoading) {
    return (
      <AppShell title={`Run ${id}`}>
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title={`Run ${id}`}>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/runs"
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Runs
          </Link>

          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-xl font-semibold text-foreground font-mono">
                  {id}
                </h1>
                <StatusBadge variant={statusVariants[run.status] ?? "error"} dot>
                  {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                </StatusBadge>
                <EnvironmentBadge environment={run.environment} />
              </div>
              <p className="text-sm text-muted-foreground">
                Workflow: <span className="text-foreground">{run.workflowName}</span> &middot;
                Triggered by: <span className="text-foreground">{run.triggeredBy}</span>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                className="h-8 gap-2"
                onClick={handleCancel}
                disabled={isCancelling || run.status !== "running"}
              >
                {isCancelling ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <XCircle className="h-3.5 w-3.5" />
                )}
                Cancel
              </Button>
              <Button 
                size="sm" 
                className="h-8 gap-2"
                onClick={handleRetry}
                disabled={isRetrying || run.status === "running"}
              >
                {isRetrying ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
                Retry
              </Button>
            </div>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            Failed to load run details. Showing cached data.
          </div>
        )}

        {/* Summary Cards */}
        <div className="mb-6 grid grid-cols-4 gap-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <Clock className="h-4 w-4" />
              <span className="text-xs">Duration</span>
            </div>
            <p className="text-lg font-semibold text-foreground font-mono">{run.duration}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <Database className="h-4 w-4" />
              <span className="text-xs">Records Processed</span>
            </div>
            <p className="text-lg font-semibold text-foreground">{run.recordsProcessed.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <CheckCircle className="h-4 w-4" />
              <span className="text-xs">Steps Completed</span>
            </div>
            <p className="text-lg font-semibold text-foreground">{run.stepsCompleted} / {run.stepsTotal}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <AlertCircle className="h-4 w-4" />
              <span className="text-xs">Error</span>
            </div>
            <p className="text-sm font-medium text-destructive truncate">
              {run.errorMessage ?? "None"}
            </p>
          </div>
        </div>

        {/* Execution Flow Card */}
        <div className="rounded-lg border border-border bg-card mb-6">
          <div className="border-b border-border p-4">
            <h2 className="text-sm font-semibold text-foreground">Execution Flow</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Steps in execution order with status</p>
          </div>
          <div className="p-4">
            <div className="flex items-center gap-2 overflow-x-auto pb-2">
              {steps.map((step, index) => {
                const StatusIcon = stepStatusIcons[step.status]
                return (
                  <div key={step.id} className="flex items-center gap-2">
                    <div className={`flex items-center gap-2 rounded-md border border-border bg-secondary/50 px-3 py-2 ${step.status === "failed" ? "border-destructive/50" : ""}`}>
                      <StatusIcon className={`h-3.5 w-3.5 ${stepStatusColors[step.status]}`} />
                      <span className="text-xs font-medium text-foreground whitespace-nowrap">{step.name}</span>
                      <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                        {step.status}
                      </span>
                    </div>
                    {index < steps.length - 1 && (
                      <div className="h-px w-4 bg-border shrink-0" />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Timeline */}
        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border p-4">
            <h2 className="text-sm font-semibold text-foreground">Execution Timeline</h2>
          </div>
          <div className="divide-y divide-border">
            {steps.map((step) => {
              const StatusIcon = stepStatusIcons[step.status]
              return (
                <div key={step.id} className="p-4">
                  <div className="flex items-start gap-4">
                    <div
                      className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border ${stepStatusColors[step.status]}`}
                    >
                      <StatusIcon className="h-3.5 w-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="text-sm font-medium text-foreground">
                          {step.name}
                        </h3>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span>{step.startedAt}</span>
                          <span className="font-mono">{step.duration}</span>
                        </div>
                      </div>
                      {step.logs && step.logs.length > 0 && (
                        <div className="mt-3 rounded-md bg-muted/50 p-3">
                          <div className="flex items-center gap-1.5 mb-2 text-muted-foreground">
                            <TerminalSquare className="h-3 w-3" />
                            <span className="text-[10px] font-medium uppercase tracking-wider">
                              Logs
                            </span>
                          </div>
                          <div className="space-y-1 font-mono text-xs">
                            {step.logs.map((log, i) => (
                              <p
                                key={i}
                                className={
                                  log.startsWith("ERROR")
                                    ? "text-destructive"
                                    : "text-muted-foreground"
                                }
                              >
                                {log}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Rollback Card */}
        <div className="mt-6 rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <RotateCcw className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">Rollback</h2>
            </div>
          </div>
          <div className="p-4">
            {/* Caution text */}
            <div className="mb-4 flex items-start gap-2 rounded-md bg-warning/10 border border-warning/20 px-3 py-2">
              <AlertTriangle className="h-4 w-4 text-warning mt-0.5 shrink-0" />
              <p className="text-xs text-warning">
                Rollback will revert this run and any changes it made. This action cannot be undone and may affect dependent workflows.
              </p>
            </div>

            {/* Rollback Error */}
            {rollbackError && (
              <div className="mb-4 flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {rollbackError}
              </div>
            )}

            {/* Rollback Actions */}
            {!showRollbackConfirm ? (
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-2"
                onClick={handleRequestRollback}
                disabled={!isAdmin}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                {isAdmin ? "Request rollback" : "Rollback (Admin only)"}
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  Are you sure you want to rollback this run?
                </span>
                <Button
                  variant="destructive"
                  size="sm"
                  className="h-8"
                  onClick={handleConfirmRollback}
                  disabled={isRollingBack}
                >
                  {isRollingBack ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                      Rolling back...
                    </>
                  ) : (
                    "Confirm"
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8"
                  onClick={handleCancelRollback}
                  disabled={isRollingBack}
                >
                  Cancel
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
