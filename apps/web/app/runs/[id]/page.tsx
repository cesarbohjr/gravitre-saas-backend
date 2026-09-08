"use client"

import { use, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { PulseDot } from "@/components/gravitre/visual"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import {
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import {
  ArrowLeft,
  RefreshCw,
  XCircle,
  Clock,
  CheckCircle,
  AlertCircle,
  Play,
  Pause,
  RotateCcw,
  AlertTriangle,
  Loader2,
} from "lucide-react"
import { fetcher } from "@/lib/fetcher"
import { approvalsApi, businessOutcomesApi, runsApi, workflowsApi } from "@/lib/api"
import { interruptRequestedDescription, interruptRequestedMessage } from "@/lib/agent-interrupts"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import { ExecutionTimeline, type ExecutionStepView } from "@/components/runs/execution-timeline"
import { RunObservabilityConsole } from "@/components/runs/run-observability-console"
import { ApprovalBatchPanel } from "@/components/runs/approval-batch-panel"
import {
  BusinessOutcomeView,
  type BusinessOutcomeDto,
} from "@/components/gravitre/business-outcome/business-outcome-view"
import { summarizeStepError, humanizeLogLine, normalizeStepLogs } from "@/lib/runs/step-summary"
import type { ApprovalBatchView, RunCompensationSummary, RunDetailResponse, RunStatus } from "@/types/api"

type StepStatus = ExecutionStepView["status"]

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
  /** Chat orchestration durable overview fields */
  isChatOrchestration?: boolean
  goal?: string
  conversationId?: string
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
  if (normalized === "awaiting_approval" || normalized === "pending_approval") return "awaiting_approval"
  return "pending"
}

function normalizeRunDetail(payload: RunDetailResponse, runId: string): { run: RunView; steps: ExecutionStepView[] } {
  const rawRun = payload.run
  const steps = (payload.steps ?? []).map((step) => {
    const started = step.startedAt ?? null
    const completed = step.completedAt ?? null
    let duration = "-"
    if (started && completed) {
      const ms = new Date(completed).getTime() - new Date(started).getTime()
      duration = formatDurationMs(ms)
    }
    const rawLogs = normalizeStepLogs(step.logs)
    const logs = [
      ...rawLogs.map((line) => humanizeLogLine(line)),
      ...(step.errorMessage && !rawLogs.some((line) => line.includes(step.errorMessage!))
        ? [humanizeLogLine(step.errorMessage)]
        : []),
    ].filter(Boolean)
    return {
      id: step.id,
      name: step.name || "Step",
      stepType: step.stepType || undefined,
      status: normalizeStepStatus(step.status),
      duration,
      startedAt: formatTimestamp(started),
      logs: logs.length > 0 ? logs : undefined,
      errorMessage: step.errorMessage,
      inputSnapshot: step.inputSnapshot ?? null,
      outputSnapshot: step.outputSnapshot ?? null,
      isRetryable: step.isRetryable,
    }
  })

  const stepsCompleted = steps.filter((s) => s.status === "completed" || s.status === "skipped").length
  const durationMs = rawRun.durationMs ?? rawRun.duration_ms ?? null
  const parameters = (rawRun.parameters ?? {}) as Record<string, unknown>
  const definition = (rawRun.definitionSnapshot ?? rawRun.definition_snapshot ?? {}) as Record<
    string,
    unknown
  >
  const isChatOrchestration =
    parameters.source === "chat_orchestration" || definition.source === "chat_orchestration"
  const goal = String(parameters.goal || parameters.label || definition.name || "").trim() || undefined
  const conversationId =
    String(
      parameters.conversation_id || parameters.conversationId || definition.conversation_id || "",
    ).trim() || undefined

  return {
    run: {
      id: String(rawRun.id ?? runId),
      workflowId: String(rawRun.workflowId ?? rawRun.workflow_id ?? ""),
      workflowName: String(rawRun.workflowName ?? rawRun.workflow_name ?? goal ?? "Workflow run"),
      status: String(rawRun.status ?? "pending") as RunStatus,
      environment: String(rawRun.environment ?? "staging"),
      triggeredBy: String(rawRun.triggeredBy ?? rawRun.triggered_by ?? "Unknown"),
      duration: formatDurationMs(durationMs),
      recordsProcessed: Number(rawRun.recordsProcessed ?? rawRun.records_processed ?? 0),
      stepsCompleted,
      stepsTotal: steps.length,
      errorMessage: String(rawRun.errorMessage ?? rawRun.error ?? rawRun.error_message ?? "") || undefined,
      startedAt: formatTimestamp(rawRun.startedAt ?? rawRun.started_at ?? rawRun.created_at),
      isChatOrchestration,
      goal,
      conversationId,
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
  awaiting_approval: Clock,
}

const stepStatusColors: Record<StepStatus, string> = {
  completed: "text-success",
  running: "text-info",
  failed: "text-destructive",
  pending: "text-warning",
  skipped: "text-muted-foreground",
  awaiting_approval: "text-warning",
}

const statusVariants: Record<string, "success" | "error" | "warning" | "info"> = {
  completed: "success",
  partial_success: "warning",
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
  const { isAdmin } = useOrgAdmin()

  const [showRollbackConfirm, setShowRollbackConfirm] = useState(false)
  const [isRollingBack, setIsRollingBack] = useState(false)
  const [rollbackError, setRollbackError] = useState<string | null>(null)
  const [isRetryingStep, setIsRetryingStep] = useState(false)
  const [isPausing, setIsPausing] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isCompensating, setIsCompensating] = useState(false)
  const [compensationSummary, setCompensationSummary] = useState<RunCompensationSummary | null>(null)
  const [isResolvingApproval, setIsResolvingApproval] = useState(false)
  const [isResuming, setIsResuming] = useState(false)

  const { data, error, isLoading, mutate, isValidating } = useSWR<RunDetailResponse>(
    `/api/runs/${id}`,
    fetcher,
    {
      refreshInterval: (latest) => {
        const status = String(latest?.run?.status ?? "").toLowerCase()
        return ["running", "paused", "awaiting_approval", "pending_approval"].includes(status) ? 2000 : 0
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
        steps: [] as ExecutionStepView[],
      }
    }
    return normalizeRunDetail(data, id)
  }, [data, id])

  const runErrorSummary = useMemo(() => summarizeStepError(run.errorMessage), [run.errorMessage])

  const canInterrupt =
    run.status === "running" ||
    run.status === "paused" ||
    run.status === "pending" ||
    run.status === "pending_approval" ||
    run.status === "approved"
  const canPause = run.status === "running"
  const canCancel =
    run.status === "running" ||
    run.status === "paused" ||
    run.status === "pending" ||
    run.status === "pending_approval" ||
    run.status === "approved"
  const canResumePaused = run.status === "paused"
  const canCompensate = run.status === "failed" && isAdmin
  const canResolveGraphApproval = run.status === "awaiting_approval" && isAdmin
  const canResolveExecuteApproval = run.status === "pending_approval" && isAdmin

  const { data: approvalBatchData, mutate: mutateApprovalBatch } = useSWR<{ batch: ApprovalBatchView | null }>(
    canResolveGraphApproval ? `/api/workflows/runs/${id}/approval-batch` : null,
    () => workflowsApi.getApprovalBatch(id),
    { refreshInterval: canResolveGraphApproval ? 2000 : 0 },
  )
  const approvalBatch = approvalBatchData?.batch ?? null

  const { data: businessOutcomePayload } = useSWR(
    id ? `/api/business-outcomes/${id}` : null,
    () => businessOutcomesApi.get(id),
    { revalidateOnFocus: false },
  )
  const businessOutcome = (businessOutcomePayload?.businessOutcome || null) as BusinessOutcomeDto | null

  async function handlePause() {
    if (!isAdmin) {
      toast.error("Admin access required to pause runs")
      return
    }
    setIsPausing(true)
    try {
      const result = await runsApi.pause(id)
      toast.success(interruptRequestedMessage("pause", { appliedEagerly: result.appliedEagerly }), {
        description: interruptRequestedDescription({ appliedEagerly: result.appliedEagerly }),
      })
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
      const result = await runsApi.cancel(id)
      toast.success(interruptRequestedMessage("cancel", { appliedEagerly: result.appliedEagerly }), {
        description: interruptRequestedDescription({ appliedEagerly: result.appliedEagerly }),
      })
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
    setIsRetryingStep(true)
    try {
      const result = await runsApi.retry(id)
      const newRunId = typeof result?.run_id === "string" ? result.run_id : null
      toast.success("New run started", {
        description: newRunId ? `Opened run ${newRunId.slice(0, 8)}…` : "A fresh execution was created.",
      })
      if (newRunId && newRunId !== id) {
        window.location.assign(`/runs/${newRunId}`)
        return
      }
      await mutate()
    } catch (err) {
      toast.error("Retry failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsRetryingStep(false)
    }
  }

  const handleRetryStep = async (stepId: string) => {
    setIsRetryingStep(true)
    try {
      await runsApi.retryStep(id, stepId)
      toast.success("Step retry started", { description: "Re-running from the failed step." })
      await mutate()
    } catch (err) {
      toast.error("Step retry failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsRetryingStep(false)
    }
  }

  const handleResumePaused = async () => {
    if (!isAdmin) {
      toast.error("Admin access required to resume this run")
      return
    }
    setIsResuming(true)
    try {
      await runsApi.resumePaused(id)
      toast.success("Run resumed", { description: "Continuing from the pause checkpoint." })
      await mutate()
    } catch (err) {
      toast.error("Resume failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsResuming(false)
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
      await Promise.all([mutate(), mutateApprovalBatch()])
    } catch (err) {
      toast.error("Could not resolve approval", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsResolvingApproval(false)
    }
  }

  const handleBatchApproval = async (
    decisions: Array<{ itemKey: string; decision: "approved" | "rejected"; comment?: string }>,
  ) => {
    if (!isAdmin) {
      toast.error("Admin access required to resume this run")
      return
    }
    setIsResolvingApproval(true)
    try {
      const result = await workflowsApi.decideApprovalBatch(id, {
        decisions: decisions.map((entry) => ({
          itemKey: entry.itemKey,
          decision: entry.decision,
          comment: entry.comment,
        })),
        resume: true,
      })
      const resumed = Boolean(result.status)
      toast.success(
        resumed ? "Batch decisions applied — run resumed" : "Batch decisions saved",
      )
      await Promise.all([mutate(), mutateApprovalBatch()])
    } catch (err) {
      toast.error("Could not submit batch approval", {
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

  const headerTitle =
    run.isChatOrchestration
      ? run.goal || "Chat orchestration"
      : run.workflowName || run.workflowId || "Workflow run"

  const headerDescription = run.isChatOrchestration
    ? `Triggered by ${run.triggeredBy}`
    : `Workflow run · Triggered by ${run.triggeredBy}`

  const runActions = (
    <div className="flex flex-wrap items-center gap-2">
      <DataFreshness
        updatedAt={data ? Date.now() : null}
        isRefreshing={isValidating}
        onRefresh={() => void mutate()}
      />
      {canResumePaused && (
        <Button
          size="sm"
          className="h-8 gap-2"
          onClick={handleResumePaused}
          disabled={!isAdmin || authLoading || isResuming}
        >
          {isResuming ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
          Resume
        </Button>
      )}
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
      <Button size="sm" className="h-8 gap-2" onClick={handleRetry} disabled={isRetryingStep}>
        {isRetryingStep ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <RefreshCw className="h-3.5 w-3.5" />
        )}
        {run.status === "running" || run.status === "paused" ? "Cancel & retry" : "Retry"}
      </Button>
    </div>
  )

  if (isLoading && !data) {
    return (
      <AppShell title={`Run ${id}`}>
        <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
          <GravitrePageHeader
            eyebrow="Execution"
            title="Run detail"
            icon={<NucleoWorkflow className="h-5 w-5" />}
            description="Loading run…"
          />
          <div className="flex flex-1 items-center justify-center px-[var(--np-page-pad)] py-8">
            <Spinner size="lg" />
          </div>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title={`Run ${id}`}>
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          className="shrink-0"
          eyebrow="Execution"
          title={headerTitle}
          description={headerDescription}
          icon={<NucleoWorkflow className="h-5 w-5" />}
          actions={runActions}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={APP_ROUTES.activity}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Activity
            </Link>
            <span className="text-border">·</span>
            <code className="font-mono text-xs text-muted-foreground">{id}</code>
            <StatusBadge variant={statusVariants[run.status] ?? "error"} dot>
              {run.status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
            </StatusBadge>
            <EnvironmentBadge
              environment={run.environment === "production" ? "production" : "staging"}
            />
          </div>
        </GravitrePageHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-[var(--np-kpi-gap)] overflow-auto px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] sm:py-3.5">
          {error && (
            <div className="flex items-center gap-2 rounded-[var(--np-radius-lg)] border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              Failed to load run details.
              <Button variant="ghost" size="sm" className="ml-auto h-7" onClick={() => mutate()}>
                Retry
              </Button>
            </div>
          )}

          {canInterrupt && !authLoading && !isAdmin && (
            <div className="flex items-center gap-2 rounded-[var(--np-radius-lg)] border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              Pause and cancel require admin access.
            </div>
          )}

          {run.stepsTotal > 0 ? (
            <GravitreSurface className="p-4" padded={false}>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span>
                  {run.status === "running"
                    ? "Progress"
                    : run.status === "completed"
                      ? "Finished"
                      : run.status === "failed"
                        ? "Stopped after failure"
                        : run.status === "cancelled"
                          ? "Cancelled"
                          : "Progress"}
                </span>
                <span className="font-mono text-foreground">
                  {run.stepsCompleted}/{run.stepsTotal} steps
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[color:var(--g-surface-2)]">
                <div
                  className={
                    run.status === "failed"
                      ? "h-full rounded-full bg-[color:var(--status-failed)] transition-all"
                      : run.status === "cancelled"
                        ? "h-full rounded-full bg-muted-foreground transition-all"
                        : run.status === "running"
                          ? "h-full rounded-full bg-[color:var(--status-running)] transition-all"
                          : "h-full rounded-full bg-[color:var(--status-verified)] transition-all"
                  }
                  style={{
                    width: `${Math.min(
                      100,
                      Math.round((run.stepsCompleted / Math.max(run.stepsTotal, 1)) * 100),
                    )}%`,
                  }}
                />
              </div>
              {run.status === "running" && run.stepsCompleted === 0 ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  Waiting for the first step to finish. If this stays stuck, use Cancel — status
                  updates immediately so you can start a new run.
                </p>
              ) : null}
            </GravitreSurface>
          ) : null}

          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
            <GravitreMetric label="Duration" value={run.duration} icon={<Clock className="h-4 w-4" />} />
            <GravitreMetric
              label="Records processed"
              value={run.recordsProcessed.toLocaleString()}
              icon={<CheckCircle className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Steps completed"
              value={`${run.stepsCompleted} / ${run.stepsTotal}`}
              icon={<Play className="h-4 w-4" />}
            />
            <GravitreMetric label="Started" value={run.startedAt} icon={<Clock className="h-4 w-4" />} />
          </section>

          <GravitreSurface className="p-4" padded={false}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-foreground">Completed work</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  What landed in connected tools (Apollo, HubSpot, Outlook, Ads, Analytics, etc.) —
                  not just whether the run finished. Open each item in the source system when a link
                  is available.
                </p>
              </div>
              {run.conversationId ? (
                <Button asChild size="sm" variant="outline" className="h-8">
                  <Link href={`/ai?c=${encodeURIComponent(run.conversationId)}`}>
                    Open conversation
                  </Link>
                </Button>
              ) : null}
            </div>
            {run.isChatOrchestration && run.goal ? (
              <p className="mb-3 text-sm text-foreground">
                <span className="text-muted-foreground">Goal: </span>
                {run.goal}
              </p>
            ) : null}
            {steps.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No step outputs recorded yet. If this run shows completed with empty work, the tools
                may not have written durable records — check connector connection and approval queue.
              </p>
            ) : (
              <ol className="space-y-2">
                {steps.map((step, index) => {
                  const snap = step.outputSnapshot || {}
                  const summary =
                    typeof snap.summary === "string"
                      ? snap.summary
                      : typeof snap.message === "string"
                        ? snap.message
                        : step.errorMessage || null
                  const external =
                    typeof snap.external_url === "string"
                      ? snap.external_url
                      : typeof snap.result_url === "string" &&
                          String(snap.result_url).startsWith("http")
                        ? String(snap.result_url)
                        : null
                  const effect =
                    typeof snap.outcome_effect === "string" ? snap.outcome_effect : null
                  const alreadyExisted = snap.already_existed === true
                  const action =
                    typeof snap.invoke_action === "string"
                      ? snap.invoke_action
                      : typeof snap.action === "string"
                        ? snap.action
                        : null
                  const portalOk =
                    !external ||
                    !external.includes("app.hubspot.com") ||
                    /^https:\/\/app\.hubspot\.com\/contacts\/\d+\//.test(external)
                  const honesty =
                    alreadyExisted || effect === "already_existed"
                      ? "Existing record — no new create proven"
                      : effect === "unknown"
                        ? "Write returned without durable proof"
                        : effect === "noop"
                          ? "No-op — vendor reported no change"
                          : effect === "accepted_async"
                            ? "Accepted asynchronously — completion not proven"
                            : null
                  return (
                    <li
                      key={step.id}
                      className="flex flex-wrap items-start justify-between gap-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-3 py-2 text-sm"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-foreground">
                          {index + 1}. {step.name}
                          <span className="ml-2 text-xs font-normal capitalize text-muted-foreground">
                            {step.status.replace(/_/g, " ")}
                          </span>
                        </p>
                        {action ? (
                          <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                            {action}
                          </p>
                        ) : null}
                        {summary ? (
                          <p className="mt-0.5 whitespace-pre-wrap text-xs text-muted-foreground">
                            {summary}
                          </p>
                        ) : null}
                        {honesty ? (
                          <p className="mt-1 text-[11px] font-medium text-warning">{honesty}</p>
                        ) : null}
                      </div>
                      {external && portalOk ? (
                        <Button asChild size="sm" variant="outline" className="h-7 shrink-0 text-xs">
                          <a href={external} target="_blank" rel="noopener noreferrer">
                            Open in source
                          </a>
                        </Button>
                      ) : null}
                    </li>
                  )
                })}
              </ol>
            )}
          </GravitreSurface>

          {runErrorSummary ? (
            <div className="rounded-[var(--np-radius-lg)] border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <p className="font-medium">{runErrorSummary.title}</p>
              {runErrorSummary.fix ? (
                <p className="mt-2 text-xs text-destructive/90">{runErrorSummary.fix}</p>
              ) : null}
            </div>
          ) : null}

          {canResumePaused && (
            <div className="rounded-[var(--np-radius-lg)] border border-warning/30 bg-warning/10 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Pause className="h-4 w-4 text-warning" />
                <h2 className="text-sm font-semibold text-foreground">Run paused</h2>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                This run was paused by an operator. Resume to continue from the saved checkpoint.
              </p>
              <Button
                size="sm"
                className="h-8 gap-2"
                disabled={!isAdmin || authLoading || isResuming}
                onClick={handleResumePaused}
              >
                {isResuming ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                Resume run
              </Button>
            </div>
          )}

          {(canResolveGraphApproval || canResolveExecuteApproval) && (
            <div className="rounded-[var(--np-radius-lg)] border border-warning/30 bg-warning/10 p-4">
              <div className="mb-3 flex items-center gap-2">
                <PulseDot tone="approval" size="md" label="Approval required" />
                <h2 className="text-sm font-semibold text-foreground">
                  {canResolveGraphApproval
                    ? "In-graph approval required"
                    : "Execute approval required"}
                </h2>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                {canResolveGraphApproval
                  ? approvalBatch
                    ? "Review each deliverable below. Approved items continue; rejected items can re-enter upstream agents."
                    : "This run paused at an approval node in the workflow graph. Approve to continue execution or reject to stop."
                  : "This run is waiting for admin approval before it can execute."}
              </p>
              {approvalBatch ? (
                <ApprovalBatchPanel
                  batch={approvalBatch}
                  disabled={!isAdmin || authLoading}
                  isSubmitting={isResolvingApproval}
                  onSubmit={handleBatchApproval}
                />
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  className="h-8 gap-2"
                  disabled={!isAdmin || authLoading || isResolvingApproval}
                  onClick={() =>
                    canResolveGraphApproval
                      ? handleGraphApproval("approved")
                      : handleExecuteApproval("approved")
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
                    canResolveGraphApproval
                      ? handleGraphApproval("rejected")
                      : handleExecuteApproval("rejected")
                  }
                >
                  <XCircle className="h-3.5 w-3.5" />
                  Reject
                </Button>
              </div>
            </div>
          )}

          <GravitreSurface padded={false}>
            <div className="border-b border-divide p-4">
              <h2 className="text-sm font-semibold text-foreground">Execution Flow</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Steps in execution order with status
              </p>
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
                          className={cn(
                            "flex items-center gap-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-3 py-2",
                            step.status === "failed" && "border-destructive/50",
                            step.status === "awaiting_approval" &&
                              "animate-pulse border-warning/50",
                          )}
                        >
                          <StatusIcon className={`h-3.5 w-3.5 ${stepStatusColors[step.status]}`} />
                          <span className="whitespace-nowrap text-xs font-medium text-foreground">
                            {step.name}
                          </span>
                          <span className="rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-1)] px-1.5 py-0.5 text-[10px] text-muted-foreground">
                            {step.status}
                          </span>
                        </div>
                        {index < steps.length - 1 && (
                          <div className="h-px w-4 shrink-0 bg-[color:var(--g-border-default)]" />
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </GravitreSurface>

          <RunObservabilityConsole runId={id} />

          <GravitreSurface padded={false}>
            <div className="border-b border-divide p-4">
              <h2 className="text-sm font-semibold text-foreground">Execution Timeline</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Full step trace with payloads, logs, and connector details. Expand steps for raw
                data.
              </p>
            </div>
            {businessOutcome ? (
              <div className="border-b border-divide p-4">
                <BusinessOutcomeView outcome={businessOutcome} density="timeline" />
                <div className="mt-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8"
                    onClick={async () => {
                      try {
                        const md = await businessOutcomesApi.exportMarkdown(id)
                        await navigator.clipboard.writeText(md)
                        toast.success("BusinessOutcome export copied (same DTO as chat/timeline)")
                      } catch (err) {
                        toast.error("Export failed", {
                          description: err instanceof Error ? err.message : "Please try again.",
                        })
                      }
                    }}
                  >
                    Copy export (same DTO)
                  </Button>
                </div>
              </div>
            ) : null}
            <ExecutionTimeline
              steps={steps}
              onRetryStep={handleRetryStep}
              isRetrying={isRetryingStep}
            />
          </GravitreSurface>

          {canCompensate && (
            <GravitreSurface padded={false}>
              <div className="border-b border-divide px-4 py-3">
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
                  <div className="mt-4 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] p-3 text-sm">
                    <p className="mb-2 font-medium text-foreground">
                      {compensationSummary.compensated} compensated · {compensationSummary.failed}{" "}
                      failed · {compensationSummary.skipped} skipped
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
            </GravitreSurface>
          )}

          <GravitreSurface padded={false}>
            <div className="border-b border-divide px-4 py-3">
              <div className="flex items-center gap-2">
                <RotateCcw className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold text-foreground">Rollback</h2>
              </div>
            </div>
            <div className="p-4">
              <div className="mb-4 flex items-start gap-2 rounded-[var(--np-radius-md)] border border-warning/20 bg-warning/10 px-3 py-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                <p className="text-xs text-warning">
                  Rollback will revert this run and any changes it made. This action cannot be
                  undone and may affect dependent workflows.
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
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
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
                    Dismiss
                  </Button>
                </div>
              )}
            </div>
          </GravitreSurface>
        </div>
      </div>
    </AppShell>
  )
}
