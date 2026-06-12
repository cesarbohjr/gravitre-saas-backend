"use client"

import { use, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
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
import { fetcher } from "@/lib/fetcher"
import { approvalsApi, runsApi, workflowsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import type { RunCompensationSummary, RunDetailResponse, RunStatus } from "@/types/api"

type StepStatus = "completed" | "running" | "failed" | "pending" | "skipped"

interface StepView {
  id: string
  name: string
  status: StepStatus
  duration: string
  startedAt: string
  logs?: string[]
  errorMessage?: string | null
}

interface RunView {
  id: string
  workflowId: string
  workflowName: string
  status: RunStatus
  environment: "production" | "staging" | string
  triggeredBy: string
  duration: string
  recordsProcessed: number
  stepsCompleted: number
  stepsTotal: number
  errorMessage?: string
  startedAt: string
}

function formatDurationMs(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "-"
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const rem = seconds % 60
  return `${minutes}m ${rem}s`
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "-"
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function normalizeStepStatus(status: string): StepStatus {
  const normalized = status.toLowerCase()
  if (normalized === "completed" || normalized === "success") return "completed"
  if (normalized === "running") return "running"
  if (normalized === "failed" || normalized === "error") return "failed"
  if (normalized === "skipped") return "skipped"
  return "pending"
}

function normalizeRunDetail(payload: RunDetailResponse, runId: string): { run: RunView; steps: StepView[] } {
  const rawRun = payload.run
  const steps = (payload.steps ?? []).map((step) => {
    const started = step.startedAt ?? null
    const completed = step.completedAt ?? null
    let duration = "-"
    if (started && completed) {
      const ms = new Date(completed).getTime() - new Date(started).getTime()
      duration = formatDurationMs(ms)
    }
    const logs = step.errorMessage ? [`ERROR: ${step.errorMessage}`] : undefined
    return {
      id: step.id,
      name: step.name || "Step",
      status: normalizeStepStatus(step.status),
      duration,
      startedAt: formatTimestamp(started),
      logs,
      errorMessage: step.errorMessage,
    }
  })

  const stepsCompleted = steps.filter((s) => s.status === "completed" || s.status === "skipped").length
  const durationMs = rawRun.durationMs ?? rawRun.duration_ms ?? null

  return {
    run: {
      id: String(rawRun.id ?? runId),
      workflowId: String(rawRun.workflowId ?? rawRun.workflow_id ?? ""),
      workflowName: String(rawRun.workflowName ?? rawRun.workflow_name ?? "Workflow run"),
      status: String(rawRun.status ?? "pending") as RunStatus,
      environment: String(rawRun.environment ?? "staging"),
      triggeredBy: String(rawRun.triggeredBy ?? rawRun.triggered_by ?? "Unknown"),
      duration: formatDurationMs(durationMs),
      recordsProcessed: Number(rawRun.recordsProcessed ?? rawRun.records_processed ?? 0),
      stepsCompleted,
      stepsTotal: steps.length,
      errorMessage: String(rawRun.errorMessage ?? rawRun.error ?? rawRun.error_message ?? "") || undefined,
      startedAt: formatTimestamp(rawRun.startedAt ?? rawRun.started_at ?? rawRun.created_at),
    },
    steps,
  }
}

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
  paused: "warning",
  cancelled: "error",
  rejected: "error",
  pending_approval: "warning",
  awaiting_approval: "warning",
  approved: "info",
}

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { user, loading: authLoading } = useAuth()
  const isAdmin = user?.role === "admin" || user?.role === "owner"

  const [showRollbackConfirm, setShowRollbackConfirm] = useState(false)
  const [isRollingBack, setIsRollingBack] = useState(false)
  const [rollbackError, setRollbackError] = useState<string | null>(null)
  const [isRetrying, setIsRetrying] = useState(false)
  const [isPausing, setIsPausing] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isCompensating, setIsCompensating] = useState(false)
  const [compensationSummary, setCompensationSummary] = useState<RunCompensationSummary | null>(null)
  const [isResolvingApproval, setIsResolvingApproval] = useState(false)

  const { data, error, isLoading, mutate } = useSWR<RunDetailResponse>(
    `/api/runs/${id}`,
    fetcher,
    {
      refreshInterval: (latest) => {
        const status = String(latest?.run?.status ?? "").toLowerCase()
        return ["running", "awaiting_approval", "pending_approval"].includes(status) ? 2000 : 0
      },
    },
  )

  const { run, steps } = useMemo(() => {
    if (!data) {
      return {
        run: {
          id,
          workflowId: "",
          workflowName: "Workflow run",
          status: "pending" as RunStatus,
          environment: "staging",
          triggeredBy: "-",
          duration: "-",
          recordsProcessed: 0,
          stepsCompleted: 0,
          stepsTotal: 0,
          startedAt: "-",
        },
        steps: [] as StepView[],
      }
    }
    return normalizeRunDetail(data, id)
  }, [data, id])

  const canInterrupt = run.status === "running" || run.status === "paused"
  const canPause = run.status === "running"
  const canCancel = run.status === "running" || run.status === "paused"
  const canCompensate = run.status === "failed" && isAdmin
  const canResolveGraphApproval = run.status === "awaiting_approval" && isAdmin
  const canResolveExecuteApproval = run.status === "pending_approval" && isAdmin

  async function handlePause() {
    if (!isAdmin) {
      toast.error("Admin access required to pause runs")
      return
    }
    setIsPausing(true)
    try {
      await runsApi.pause(id)
      toast.success("Pause requested", { description: "Run will stop before the next step." })
      await mutate()
    } catch (err) {
      toast.error("Pause failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsPausing(false)
    }
  }

  async function handleCancel() {
    if (!isAdmin) {
      toast.error("Admin access required to cancel runs")
      return
    }
    setIsCancelling(true)
    try {
      await runsApi.cancel(id)
      toast.success("Cancel requested", { description: "Run will stop before the next step." })
      await mutate()
    } catch (err) {
      toast.error("Cancel failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsCancelling(false)
    }
  }

  const handleRetry = async () => {
    setIsRetrying(true)
    try {
      await runsApi.retry(id)
      toast.success("Retry started")
      await mutate()
    } catch (err) {
      toast.error("Retry failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsRetrying(false)
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
      await runsApi.rollback(id)
      setShowRollbackConfirm(false)
      toast.success("Rollback initiated")
      await mutate()
    } catch (err) {
      setRollbackError(err instanceof Error ? err.message : "Failed to initiate rollback. Please try again.")
    } finally {
      setIsRollingBack(false)
    }
  }

  const handleCompensate = async () => {
    if (!isAdmin) {
      toast.error("Admin access required to run compensations")
      return
    }
    setIsCompensating(true)
    try {
      const summary = await runsApi.compensate(id)
      setCompensationSummary(summary)
      toast.success("Compensation run finished", {
        description: `${summary.compensated} compensated · ${summary.failed} failed`,
      })
      await mutate()
    } catch (err) {
      toast.error("Compensation failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsCompensating(false)
    }
  }

  const handleGraphApproval = async (decision: "approved" | "rejected") => {
    if (!isAdmin) {
      toast.error("Admin access required to resume this run")
      return
    }
    setIsResolvingApproval(true)
    try {
      await workflowsApi.resumeRun(id, { decision })
      toast.success(decision === "approved" ? "Approval recorded — run resumed" : "Run rejected")
      await mutate()
    } catch (err) {
      toast.error("Could not resolve approval", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsResolvingApproval(false)
    }
  }

  const handleExecuteApproval = async (decision: "approved" | "rejected") => {
    if (!isAdmin) {
      toast.error("Admin access required to approve execute runs")
      return
    }
    setIsResolvingApproval(true)
    try {
      if (decision === "approved") {
        await approvalsApi.approve(id)
        toast.success("Run approved")
      } else {
        await approvalsApi.reject(id)
        toast.success("Run rejected")
      }
      await mutate()
    } catch (err) {
      toast.error("Approval action failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsResolvingApproval(false)
    }
  }

  const handleCancelRollback = () => {
    setShowRollbackConfirm(false)
    setRollbackError(null)
  }

  if (isLoading && !data) {
    return (
      <AppShell title={`Run ${id}`}>
        <div className="flex h-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title={`Run ${id}`}>
      <div className="p-6">
        <div className="mb-6">
          <Link
            href="/runs"
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Runs
          </Link>

          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <h1 className="font-mono text-xl font-semibold text-foreground">{id}</h1>
                <StatusBadge variant={statusVariants[run.status] ?? "error"} dot>
                  {run.status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </StatusBadge>
                <EnvironmentBadge environment={run.environment === "production" ? "production" : "staging"} />
              </div>
              <p className="text-sm text-muted-foreground">
                Workflow: <span className="text-foreground">{run.workflowName || run.workflowId || "—"}</span> ·
                Triggered by: <span className="text-foreground">{run.triggeredBy}</span>
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {canPause && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-2"
                  onClick={handlePause}
                  disabled={!isAdmin || authLoading || isPausing}
                >
                  {isPausing ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Pause className="h-3.5 w-3.5" />
                  )}
                  Pause
                </Button>
              )}
              {canCancel && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-2"
                  onClick={handleCancel}
                  disabled={!isAdmin || authLoading || isCancelling}
                >
                  {isCancelling ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5" />
                  )}
                  Cancel
                </Button>
              )}
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

        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            Failed to load run details.
            <Button variant="ghost" size="sm" className="ml-auto h-7" onClick={() => mutate()}>
              Retry
            </Button>
          </div>
        )}

        {canInterrupt && !authLoading && !isAdmin && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Pause and cancel require admin access.
          </div>
        )}

        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-2 flex items-center gap-2 text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span className="text-xs">Duration</span>
            </div>
            <p className="font-mono text-lg font-semibold text-foreground">{run.duration}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-2 flex items-center gap-2 text-muted-foreground">
              <Database className="h-4 w-4" />
              <span className="text-xs">Records Processed</span>
            </div>
            <p className="text-lg font-semibold text-foreground">{run.recordsProcessed.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-2 flex items-center gap-2 text-muted-foreground">
              <CheckCircle className="h-4 w-4" />
              <span className="text-xs">Steps Completed</span>
            </div>
            <p className="text-lg font-semibold text-foreground">
              {run.stepsCompleted} / {run.stepsTotal}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-2 flex items-center gap-2 text-muted-foreground">
              <AlertCircle className="h-4 w-4" />
              <span className="text-xs">Started</span>
            </div>
            <p className="truncate text-sm font-medium text-foreground">{run.startedAt}</p>
          </div>
        </div>

        {run.errorMessage ? (
          <div className="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {run.errorMessage}
          </div>
        ) : null}

        {(canResolveGraphApproval || canResolveExecuteApproval) && (
          <div className="mb-6 rounded-lg border border-warning/30 bg-warning/10 p-4">
            <div className="mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              <h2 className="text-sm font-semibold text-foreground">
                {canResolveGraphApproval ? "In-graph approval required" : "Execute approval required"}
              </h2>
            </div>
            <p className="mb-4 text-sm text-muted-foreground">
              {canResolveGraphApproval
                ? "This run paused at an approval node in the workflow graph. Approve to continue execution or reject to stop."
                : "This run is waiting for admin approval before it can execute."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                className="h-8 gap-2"
                disabled={!isAdmin || authLoading || isResolvingApproval}
                onClick={() =>
                  canResolveGraphApproval ? handleGraphApproval("approved") : handleExecuteApproval("approved")
                }
              >
                {isResolvingApproval ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <CheckCircle className="h-3.5 w-3.5" />
                )}
                Approve
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-2"
                disabled={!isAdmin || authLoading || isResolvingApproval}
                onClick={() =>
                  canResolveGraphApproval ? handleGraphApproval("rejected") : handleExecuteApproval("rejected")
                }
              >
                <XCircle className="h-3.5 w-3.5" />
                Reject
              </Button>
            </div>
          </div>
        )}

        <div className="mb-6 rounded-lg border border-border bg-card">
          <div className="border-b border-border p-4">
            <h2 className="text-sm font-semibold text-foreground">Execution Flow</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Steps in execution order with status</p>
          </div>
          <div className="p-4">
            {steps.length === 0 ? (
              <p className="text-sm text-muted-foreground">No steps recorded yet.</p>
            ) : (
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {steps.map((step, index) => {
                  const StatusIcon = stepStatusIcons[step.status]
                  return (
                    <div key={step.id} className="flex items-center gap-2">
                      <div
                        className={`flex items-center gap-2 rounded-md border border-border bg-secondary/50 px-3 py-2 ${step.status === "failed" ? "border-destructive/50" : ""}`}
                      >
                        <StatusIcon className={`h-3.5 w-3.5 ${stepStatusColors[step.status]}`} />
                        <span className="whitespace-nowrap text-xs font-medium text-foreground">{step.name}</span>
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {step.status}
                        </span>
                      </div>
                      {index < steps.length - 1 && <div className="h-px w-4 shrink-0 bg-border" />}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border p-4">
            <h2 className="text-sm font-semibold text-foreground">Execution Timeline</h2>
          </div>
          <div className="divide-y divide-border">
            {steps.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground">Waiting for step output…</div>
            ) : (
              steps.map((step) => {
                const StatusIcon = stepStatusIcons[step.status]
                return (
                  <div key={step.id} className="p-4">
                    <div className="flex items-start gap-4">
                      <div
                        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border ${stepStatusColors[step.status]}`}
                      >
                        <StatusIcon className="h-3.5 w-3.5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center justify-between">
                          <h3 className="text-sm font-medium text-foreground">{step.name}</h3>
                          <div className="flex items-center gap-4 text-xs text-muted-foreground">
                            <span>{step.startedAt}</span>
                            <span className="font-mono">{step.duration}</span>
                          </div>
                        </div>
                        {step.logs && step.logs.length > 0 && (
                          <div className="mt-3 rounded-md bg-muted/50 p-3">
                            <div className="mb-2 flex items-center gap-1.5 text-muted-foreground">
                              <TerminalSquare className="h-3 w-3" />
                              <span className="text-[10px] font-medium uppercase tracking-wider">Logs</span>
                            </div>
                            <div className="space-y-1 font-mono text-xs">
                              {step.logs.map((log, i) => (
                                <p
                                  key={i}
                                  className={log.startsWith("ERROR") ? "text-destructive" : "text-muted-foreground"}
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
              })
            )}
          </div>
        </div>

        {canCompensate && (
          <div className="mb-6 rounded-lg border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <RotateCcw className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold text-foreground">Compensation</h2>
              </div>
            </div>
            <div className="p-4">
              <p className="mb-4 text-sm text-muted-foreground">
                Run compensating actions for side effects recorded during this failed run.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-2"
                onClick={handleCompensate}
                disabled={!isAdmin || authLoading || isCompensating}
              >
                {isCompensating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="h-3.5 w-3.5" />
                )}
                {isAdmin ? "Run compensation" : "Compensation (Admin only)"}
              </Button>
              {compensationSummary && (
                <div className="mt-4 rounded-md border border-border bg-muted/30 p-3 text-sm">
                  <p className="mb-2 font-medium text-foreground">
                    {compensationSummary.compensated} compensated · {compensationSummary.failed} failed ·{" "}
                    {compensationSummary.skipped} skipped
                  </p>
                  {compensationSummary.results.length > 0 && (
                    <ul className="space-y-1 font-mono text-xs text-muted-foreground">
                      {compensationSummary.results.map((result) => (
                        <li key={result.recordId}>
                          {result.action}: {result.status}
                          {result.error ? ` — ${result.error}` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mt-6 rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <RotateCcw className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">Rollback</h2>
            </div>
          </div>
          <div className="p-4">
            <div className="mb-4 flex items-start gap-2 rounded-md border border-warning/20 bg-warning/10 px-3 py-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <p className="text-xs text-warning">
                Rollback will revert this run and any changes it made. This action cannot be undone and may affect
                dependent workflows.
              </p>
            </div>

            {rollbackError && (
              <div className="mb-4 flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {rollbackError}
              </div>
            )}

            {!showRollbackConfirm ? (
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-2"
                onClick={handleRequestRollback}
                disabled={!isAdmin || authLoading}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                {isAdmin ? "Request rollback" : "Rollback (Admin only)"}
              </Button>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-muted-foreground">Are you sure you want to rollback this run?</span>
                <Button
                  variant="destructive"
                  size="sm"
                  className="h-8"
                  onClick={handleConfirmRollback}
                  disabled={isRollingBack}
                >
                  {isRollingBack ? (
                    <>
                      <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      Rolling back...
                    </>
                  ) : (
                    "Confirm"
                  )}
                </Button>
                <Button variant="ghost" size="sm" className="h-8" onClick={handleCancelRollback} disabled={isRollingBack}>
                  Dismiss
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
