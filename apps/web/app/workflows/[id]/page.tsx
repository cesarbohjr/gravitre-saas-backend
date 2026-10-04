"use client"

import { use, useRef, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { formatStatusLabel } from "@/components/gravitre/status-badge"
import { StatusChip } from "@/components/gravitre/visual"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { Button } from "@/components/ui/button"
import { WorkDecisionDialog } from "@/components/gravitre/work-decision-dialog"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { WorkflowPreRunPanel } from "@/components/workflows/workflow-pre-run-panel"
import type { IntelligenceDrawerNode } from "@/components/workflows/intelligence-drawer"
import { workflowsApi, runsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import { ArrowLeft, Calendar, ChevronRight, Loader2, Play, Rocket, GitBranch } from "lucide-react"

export default function WorkflowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { user } = useAuth()
  const router = useRouter()
  const mutationLock = useRef(false)
  const [decision, setDecision] = useState<"run" | "cancel" | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  const {
    data: workflow,
    error,
    isLoading,
    mutate: mutateWorkflow,
  } = useSWR(user ? ["workflow-detail", id] : null, () => workflowsApi.get(id))
  usePublishGravitreAISelection({
    kind: "workflow",
    id,
    label: workflow?.name?.trim() || id,
  })

  const {
    data: builder,
    error: builderError,
    isLoading: builderLoading,
    mutate: mutateBuilder,
  } = useSWR(user ? ["workflow-builder", id] : null, () => workflowsApi.getBuilder(id))

  const {
    data: latestRuns,
    error: latestError,
    isLoading: latestLoading,
    mutate: mutateLatestRuns,
  } = useSWR(
    user ? ["workflow-latest-run", id] : null,
    () => runsApi.list({ workflow_id: id, limit: 1 }),
    { refreshInterval: 5000 },
  )
  const latestRun = latestRuns?.runs?.[0]

  const {
    data: activeRuns,
    error: activeError,
    isLoading: activeLoading,
    mutate: mutateActiveRuns,
  } = useSWR(
    user ? ["workflow-active-run", id] : null,
    () => runsApi.list({ workflow_id: id, status: "running", limit: 1 }),
    { refreshInterval: 4000 },
  )
  const activeRun = activeRuns?.runs?.[0]
  const activeRunId = activeRun?.id ? String(activeRun.id) : null

  const intelligenceNodes: IntelligenceDrawerNode[] = (builder?.nodes ?? []).map((node) => ({
    id: String(node.id),
    name: String(node.name ?? node.title ?? "Step"),
    type: String(node.node_type ?? "task"),
  }))

  const isActive = String(workflow?.status ?? "").toLowerCase() === "active"
  const canRunLive =
    intelligenceNodes.length > 0 &&
    !builderError &&
    !builderLoading &&
    !activeError &&
    !activeLoading &&
    Boolean(activeRuns) &&
    Boolean(workflow) &&
    !error
  const hasActiveRun = Boolean(activeRunId)

  const handleRunNow = async () => {
    if (!canRunLive || hasActiveRun || mutationLock.current) throw new Error("Execution readiness changed. Refresh the workflow and active execution check before continuing.")
    mutationLock.current = true
    setIsRunning(true)
    try {
      if (!isActive) {
        await workflowsApi.update(id, { status: "active" })
        void mutateWorkflow().catch(() => undefined)
      }
      const result = await workflowsApi.execute({ workflow_id: id })
      const runId = result.run_id
      if (!runId)
        throw new Error(
          "The execution request returned no run ID. Check run history before trying again.",
        )
      toast.success("Production execution requested", {
        description: result.status
          ? `Status: ${formatStatusLabel(result.status)}`
          : "Execution status not reported.",
      })
      void Promise.allSettled([mutateLatestRuns(), mutateActiveRuns()])
      if (runId) {
        router.push(`/runs/${runId}`)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start production run"
      const payload =
        err && typeof err === "object" && "payload" in err
          ? (err as { payload?: { detail?: { active_run_id?: string } } }).payload
          : undefined
      const blockedId =
        typeof payload?.detail?.active_run_id === "string"
          ? payload.detail.active_run_id
          : activeRunId
      toast.error(message, {
        action: blockedId
          ? {
              label: "Open run",
              onClick: () => router.push(`/runs/${blockedId}`),
            }
          : undefined,
      })
      void mutateActiveRuns().catch(() => undefined)
      throw err
    } finally {
      mutationLock.current = false
      setIsRunning(false)
    }
  }

  const handleCancelActiveRun = async () => {
    if (!activeRunId || mutationLock.current) return
    mutationLock.current = true
    setIsRunning(true)
    try {
      const result = await runsApi.cancel(activeRunId)
      toast.success(result.appliedEagerly ? "Active run cancelled." : "Cancel requested.", {
        description: result.appliedEagerly
          ? "You can start a new run now."
          : "Execution stops before the next step.",
      })
      void Promise.allSettled([mutateLatestRuns(), mutateActiveRuns()])
    } catch (err) {
      throw err
    } finally {
      mutationLock.current = false
      setIsRunning(false)
    }
  }

  return (
    <AppShell title={workflow?.name ?? "Workflow"}>
      <div
        className="mx-auto max-w-5xl space-y-6 pb-24 [&_[data-slot=button]]:min-h-11"
        data-composition="operate"
      >
        <GravitrePageHeader
          eyebrow="Workflows"
          title={
            isLoading
              ? "Loading…"
              : error && !workflow
                ? "Workflow unavailable"
                : (workflow?.name ?? "Workflow")
          }
          description={workflow?.description ? workflow.description : undefined}
          icon={<NucleoWorkflow className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap gap-2">
              <AskGravitreSummonButton />
              <Button variant="ghost" size="sm" asChild>
                <Link href="/workflows">
                  <ArrowLeft className="mr-1 h-4 w-4" />
                  Back
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/runs?workflow_id=${encodeURIComponent(id)}`}>
                  <Play className="h-4 w-4 mr-1" />
                  Run history
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/workflows/${id}/builder`}>
                  <GitBranch className="h-4 w-4 mr-1" />
                  Open builder
                </Link>
              </Button>
              <Button
                size="sm"
                disabled={!canRunLive || isRunning || isLoading || Boolean(error) || hasActiveRun}
                onClick={() => setDecision("run")}
              >
                {isRunning ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <Rocket className="h-4 w-4 mr-1" />
                )}
                Run now
              </Button>
            </div>
          }
        >
          {workflow ? (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {workflow.status ? (
                <StatusChip status={String(workflow.status)}>
                  {formatStatusLabel(String(workflow.status))}
                </StatusChip>
              ) : null}
              {["production", "staging"].includes(workflow.environment ?? "") ? (
                <EnvironmentBadge
                  environment={workflow.environment === "production" ? "production" : "staging"}
                />
              ) : null}
            </div>
          ) : null}
        </GravitrePageHeader>

        <div className="space-y-6 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]">
          {error ? (
            <WorkSectionErrorCard
              title="Workflow could not refresh"
              error={error}
              onRetry={() => void mutateWorkflow()}
            />
          ) : null}
          {isLoading && !workflow ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading workflow…
            </div>
          ) : workflow ? (
            <>
              {builder ? <WorkflowPreRunPanel workflowId={id} nodes={intelligenceNodes} /> : null}
              {activeError ? (
                <WorkSectionErrorCard
                  title="Active execution check unavailable"
                  message="Refresh this check before starting another production execution."
                  error={activeError}
                  onRetry={() => void mutateActiveRuns()}
                />
              ) : activeLoading ? (
                <p role="status" className="text-sm text-muted-foreground">
                  Checking active executions…
                </p>
              ) : null}

              {hasActiveRun ? (
                <section className="border-b border-divide py-4">
                  <h2 className="flex items-center gap-2 text-base font-medium">
                    <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                    Run in progress
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    A one-time production run is active. Finished runs leave this state; only
                    schedules create later reruns.
                  </p>
                  <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-muted-foreground">
                      Run{" "}
                      <Link
                        href={`/runs/${activeRunId}`}
                        className="font-mono text-foreground underline-offset-4 hover:underline"
                      >
                        {activeRunId?.slice(0, 8)}…
                      </Link>
                    </p>
                    <div className="flex flex-wrap gap-2 shrink-0">
                      <Button size="sm" variant="outline" asChild>
                        <Link href={`/runs/${activeRunId}`}>View progress</Link>
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={isRunning}
                        onClick={() => setDecision("cancel")}
                      >
                        Cancel run
                      </Button>
                    </div>
                  </div>
                </section>
              ) : null}

              <section className="border-b border-divide py-4">
                <h2 className="flex items-center gap-2 text-base font-medium">
                  <Rocket className="h-4 w-4 text-primary" />
                  Run in production
                </h2>
                <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                  Run now starts one execution. Use Schedule runs for daily, weekly, or monthly
                  repeats. “Workflow is active” means the workflow is enabled — not that a run is in
                  progress.
                </p>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-muted-foreground max-w-xl">
                    {hasActiveRun
                      ? "A run is already in progress. Cancel it above, or wait for it to finish, before starting another."
                      : isActive
                        ? "Ready for a one-time production run using the current builder graph and linked connectors."
                        : "Workflow is not enabled yet. Activate & run turns it on, then starts a production execution."}
                    {!canRunLive ? " Add at least one step in the builder first." : null}
                  </p>
                  <div className="flex flex-wrap gap-2 shrink-0">
                    <Button variant="outline" size="sm" asChild>
                      <Link href={`/workflows/${id}/schedules`}>
                        <Calendar className="h-4 w-4 mr-1" />
                        Schedule runs
                      </Link>
                    </Button>
                    <Button
                      size="sm"
                      disabled={!canRunLive || isRunning || hasActiveRun}
                      onClick={() => setDecision("run")}
                    >
                      {isRunning ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <Rocket className="h-4 w-4 mr-1" />
                      )}
                      {isActive ? "Run now" : "Activate & run"}
                    </Button>
                  </div>
                </div>
              </section>

              <section className="border-b border-divide py-4">
                <h2 className="text-base font-medium">Latest run</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Most recent run for this workflow only. Completed one-time runs show as completed
                  — not running.
                </p>
                <div className="mt-3 space-y-3">
                  {latestError ? (
                    <WorkSectionErrorCard
                      title="Run history could not refresh"
                      error={latestError}
                      onRetry={() => void mutateLatestRuns()}
                    />
                  ) : null}
                  {latestLoading && !latestRuns ? (
                    <p role="status">Loading run history…</p>
                  ) : !latestRun && !latestError && latestRuns ? (
                    <p className="text-sm text-muted-foreground">
                      No runs yet. Use <span className="font-medium text-foreground">Run now</span>{" "}
                      or <span className="font-medium text-foreground">Schedule runs</span> above.
                    </p>
                  ) : latestRun ? (
                    <>
                      <div className="flex flex-wrap items-center gap-2">
                        {latestRun.status ? (
                          <StatusChip status={String(latestRun.status)}>
                            {formatStatusLabel(String(latestRun.status))}
                          </StatusChip>
                        ) : null}
                        {latestRun.id ? (
                          <Button variant="link" className="h-auto p-0" asChild>
                            <Link href={`/runs/${latestRun.id}`}>
                              View run {String(latestRun.id).slice(0, 8)}…
                            </Link>
                          </Button>
                        ) : null}
                      </div>
                      {latestRun.status === "failed" || latestRun.status === "cancelled" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={!canRunLive || isRunning || hasActiveRun}
                          onClick={() => setDecision("run")}
                        >
                          Run again
                        </Button>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </section>

              <section className="border-b border-divide py-4">
                <h2 className="text-base font-medium">Canvas steps</h2>
                <div className="mt-3">
                  {builderError ? (
                    <WorkSectionErrorCard
                      title="Canvas could not refresh"
                      error={builderError}
                      onRetry={() => void mutateBuilder()}
                    />
                  ) : null}
                  {builderLoading && !builder ? (
                    <p role="status">Loading canvas…</p>
                  ) : !builder ? null : intelligenceNodes.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No steps yet.{" "}
                      <Link
                        href={`/workflows/${id}/builder`}
                        className="text-primary underline-offset-4 hover:underline"
                      >
                        Open the builder
                      </Link>{" "}
                      to design this workflow.
                    </p>
                  ) : (
                    <ol className="space-y-2">
                      {intelligenceNodes.map((node, index) => (
                        <li
                          key={node.id}
                          className="flex items-center justify-between gap-2 border-b border-divide py-2 text-sm"
                        >
                          <span>
                            <span className="text-muted-foreground mr-2">{index + 1}.</span>
                            {node.name}
                          </span>
                          <BadgeType type={node.type} />
                        </li>
                      ))}
                    </ol>
                  )}
                  <Button variant="link" className="mt-3 h-auto p-0" asChild>
                    <Link href={`/workflows/${id}/builder`}>
                      Edit in builder
                      <ChevronRight className="h-4 w-4 ml-0.5" />
                    </Link>
                  </Button>
                </div>
              </section>
            </>
          ) : null}
        </div>
      </div>
      {decision ? (
        <WorkDecisionDialog
          title={
            decision === "cancel"
              ? "Cancel this execution?"
              : isActive
                ? "Run this workflow in production?"
                : "Activate and run this workflow?"
          }
          description={
            decision === "cancel"
              ? `Request cancellation of run ${activeRunId}. Execution may stop before its next step.`
              : `${workflow?.name ?? "This workflow"} will use its saved graph and linked connectors for one production execution.${isActive ? "" : " This also enables the workflow; it stays enabled if execution fails."} Schedules are managed separately.`
          }
          actionLabel={
            decision === "cancel"
              ? "Request cancellation"
              : isActive
                ? "Run in production"
                : "Activate & run"
          }
          cancelLabel="Go back"
          busyLabel={decision === "cancel" ? "Requesting cancellation…" : "Requesting execution…"}
          destructive={decision === "cancel"}
          onCancel={() => setDecision(null)}
          onConfirm={decision === "cancel" ? handleCancelActiveRun : handleRunNow}
        />
      ) : null}
    </AppShell>
  )
}

function BadgeType({ type }: { type: string }) {
  return (
    <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground font-medium">
      {type.replace(/_/g, " ")}
    </span>
  )
}
