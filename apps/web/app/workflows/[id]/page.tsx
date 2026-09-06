"use client"

import { use, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { formatStatusLabel } from "@/components/gravitre/status-badge"
import { StatusChip } from "@/components/gravitre/visual"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { WorkflowPreRunPanel } from "@/components/workflows/workflow-pre-run-panel"
import type { IntelligenceDrawerNode } from "@/components/workflows/intelligence-drawer"
import { workflowsApi, runsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import {
  ArrowLeft,
  Calendar,
  ChevronRight,
  ExternalLink,
  Loader2,
  Play,
  Rocket,
  Sparkles,
  Workflow,
} from "lucide-react"

export default function WorkflowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { user } = useAuth()
  const router = useRouter()
  const [isRunning, setIsRunning] = useState(false)

  const { data: workflow, error, isLoading, mutate: mutateWorkflow } = useSWR(
    user ? ["workflow-detail", id] : null,
    () => workflowsApi.get(id),
  )

  const { data: builder } = useSWR(user ? ["workflow-builder", id] : null, () => workflowsApi.getBuilder(id))

  const { data: latestRuns, mutate: mutateLatestRuns } = useSWR(
    user ? ["workflow-latest-run", id] : null,
    () => runsApi.list({ workflow_id: id, limit: 1 }),
    { refreshInterval: 5000 },
  )
  const latestRun = latestRuns?.runs?.[0]

  const { data: activeRuns, mutate: mutateActiveRuns } = useSWR(
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
  const canRunLive = intelligenceNodes.length > 0
  const hasActiveRun = Boolean(activeRunId)

  const handleRunNow = async () => {
    if (!canRunLive || isRunning) return
    setIsRunning(true)
    try {
      if (!isActive) {
        await workflowsApi.update(id, { status: "active" })
        await mutateWorkflow()
      }
      const result = await workflowsApi.execute({ workflow_id: id })
      const runId = result.run_id
      toast.success("Production run started")
      await Promise.all([mutateLatestRuns(), mutateActiveRuns()])
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
        typeof payload?.detail?.active_run_id === "string" ? payload.detail.active_run_id : activeRunId
      toast.error(message, {
        action: blockedId
          ? {
              label: "Open run",
              onClick: () => router.push(`/runs/${blockedId}`),
            }
          : undefined,
      })
      await mutateActiveRuns()
    } finally {
      setIsRunning(false)
    }
  }

  const handleCancelActiveRun = async () => {
    if (!activeRunId) return
    setIsRunning(true)
    try {
      const result = await runsApi.cancel(activeRunId)
      toast.success(
        result.appliedEagerly ? "Active run cancelled." : "Cancel requested.",
        {
          description: result.appliedEagerly
            ? "You can start a new run now."
            : "Execution stops before the next step.",
        },
      )
      await Promise.all([mutateLatestRuns(), mutateActiveRuns()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to cancel active run")
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <AppShell title={workflow?.name ?? "Workflow"}>
      <div className="mx-auto max-w-5xl p-4 sm:p-6 space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <Button variant="ghost" size="sm" className="-ml-2 h-8" asChild>
              <Link href="/workflows">
                <ArrowLeft className="h-4 w-4 mr-1" />
                Workflows
              </Link>
            </Button>
            {isLoading ? (
              <Skeleton className="h-8 w-64" />
            ) : error ? (
              <h1 className="text-xl font-semibold">Workflow unavailable</h1>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Workflow className="h-5 w-5 text-muted-foreground" />
                  <h1 className="text-xl font-semibold tracking-tight">{workflow?.name ?? "Workflow"}</h1>
                  {workflow?.status ? (
                    <StatusChip status={String(workflow.status)}>
                      {formatStatusLabel(String(workflow.status))}
                    </StatusChip>
                  ) : null}
                  {workflow?.environment ? (
                    <EnvironmentBadge
                      environment={workflow.environment === "production" ? "production" : "staging"}
                    />
                  ) : null}
                </div>
                {workflow?.description ? (
                  <p className="text-sm text-muted-foreground max-w-2xl">{workflow.description}</p>
                ) : null}
              </>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href={`/runs?workflow_id=${encodeURIComponent(id)}`}>
                <Play className="h-4 w-4 mr-1" />
                Run history
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/workflows/${id}/builder`}>
                <Sparkles className="h-4 w-4 mr-1" />
                Open builder
              </Link>
            </Button>
            <Button
              size="sm"
              disabled={!canRunLive || isRunning || isLoading || Boolean(error) || hasActiveRun}
              onClick={() => void handleRunNow()}
            >
              {isRunning ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Rocket className="h-4 w-4 mr-1" />
              )}
              Run now
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading workflow…
          </div>
        ) : error ? (
          <Card className="border-destructive/30">
            <CardContent className="pt-6 text-sm text-destructive">
              Failed to load workflow. It may have been deleted or you may lack access.
            </CardContent>
          </Card>
        ) : (
          <>
            <WorkflowPreRunPanel workflowId={id} nodes={intelligenceNodes} />

            {hasActiveRun ? (
              <Card className="border-blue-500/40 bg-blue-500/[0.06]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                    Run in progress
                  </CardTitle>
                  <CardDescription>
                    A one-time production run is active. Finished runs leave this state; only schedules
                    create later reruns.
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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
                      onClick={() => void handleCancelActiveRun()}
                    >
                      Cancel run
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : null}

            <Card className="border-primary/25 bg-primary/[0.03]">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Rocket className="h-4 w-4 text-primary" />
                  Run in production
                </CardTitle>
                <CardDescription>
                  Run now starts one execution. Use Schedule runs for daily, weekly, or monthly repeats.
                  “Workflow is active” means the workflow is enabled — not that a run is in progress.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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
                    onClick={() => void handleRunNow()}
                  >
                    {isRunning ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <Rocket className="h-4 w-4 mr-1" />
                    )}
                    {isActive ? "Run now" : "Activate & run"}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Latest run</CardTitle>
                <CardDescription>
                  Most recent run for this workflow only. Completed one-time runs show as completed — not
                  running.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {!latestRun ? (
                  <p className="text-sm text-muted-foreground">
                    No runs yet. Use <span className="font-medium text-foreground">Run now</span> or{" "}
                    <span className="font-medium text-foreground">Schedule runs</span> above.
                  </p>
                ) : (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      {latestRun.status ? (
                        <StatusChip status={String(latestRun.status)}>
                          {formatStatusLabel(String(latestRun.status))}
                        </StatusChip>
                      ) : null}
                      {latestRun.id ? (
                        <Button variant="link" className="h-auto p-0" asChild>
                          <Link href={`/runs/${latestRun.id}`}>View run {String(latestRun.id).slice(0, 8)}…</Link>
                        </Button>
                      ) : null}
                    </div>
                    {latestRun.status === "failed" || latestRun.status === "cancelled" ? (
                      <Button size="sm" variant="outline" disabled={isRunning || hasActiveRun} onClick={() => void handleRunNow()}>
                        Run again
                      </Button>
                    ) : null}
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Canvas steps</CardTitle>
              </CardHeader>
              <CardContent>
                {intelligenceNodes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No steps yet.{" "}
                    <Link href={`/workflows/${id}/builder`} className="text-primary underline-offset-4 hover:underline">
                      Open the builder
                    </Link>{" "}
                    to design this workflow.
                  </p>
                ) : (
                  <ol className="space-y-2">
                    {intelligenceNodes.map((node, index) => (
                      <li
                        key={node.id}
                        className="flex items-center justify-between gap-2 rounded-md border border-border/70 px-3 py-2 text-sm"
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
              </CardContent>
            </Card>

            <Card className="border-dashed">
              <CardContent className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-6">
                <div>
                  <p className="text-sm font-medium">Builder intelligence</p>
                  <p className="text-xs text-muted-foreground">
                    Timing estimates, risk scan, and dry run are also available while editing the canvas.
                  </p>
                </div>
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/workflows/${id}/builder`}>
                    Open builder
                    <ExternalLink className="h-3.5 w-3.5 ml-1" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </AppShell>
  )
}

function BadgeType({ type }: { type: string }) {
  return (
    <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
      {type.replace(/_/g, " ")}
    </span>
  )
}
