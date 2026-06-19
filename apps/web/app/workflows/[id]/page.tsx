"use client"

import { use } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { AutoStatusBadge } from "@/components/gravitre/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { WorkflowPreRunPanel } from "@/components/workflows/workflow-pre-run-panel"
import type { IntelligenceDrawerNode } from "@/components/workflows/intelligence-drawer"
import { workflowsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import {
  ArrowLeft,
  Calendar,
  ChevronRight,
  ExternalLink,
  Loader2,
  Play,
  Sparkles,
  Workflow,
} from "lucide-react"

export default function WorkflowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { user } = useAuth()

  const { data: workflow, error, isLoading } = useSWR(
    user ? ["workflow-detail", id] : null,
    () => workflowsApi.get(id),
  )

  const { data: builder } = useSWR(user ? ["workflow-builder", id] : null, () => workflowsApi.getBuilder(id))

  const intelligenceNodes: IntelligenceDrawerNode[] = (builder?.nodes ?? []).map((node) => ({
    id: String(node.id),
    name: String(node.name ?? node.title ?? "Step"),
    type: String(node.node_type ?? "task"),
  }))

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
              <h1 className="text-2xl font-semibold">Workflow unavailable</h1>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Workflow className="h-5 w-5 text-muted-foreground" />
                  <h1 className="text-2xl font-semibold tracking-tight">{workflow?.name ?? "Workflow"}</h1>
                  {workflow?.status ? <AutoStatusBadge status={workflow.status} /> : null}
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
              <Link href={`/workflows/${id}/schedules`}>
                <Calendar className="h-4 w-4 mr-1" />
                Schedules
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/runs?workflow_id=${encodeURIComponent(id)}`}>
                <Play className="h-4 w-4 mr-1" />
                Runs
              </Link>
            </Button>
            <Button size="sm" asChild>
              <Link href={`/workflows/${id}/builder`}>
                <Sparkles className="h-4 w-4 mr-1" />
                Open builder
              </Link>
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
                  <p className="text-sm font-medium">Full intelligence drawer</p>
                  <p className="text-xs text-muted-foreground">
                    Dry run, risk scan, and simulate are also available in the builder intelligence panel.
                  </p>
                </div>
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/workflows/${id}/builder`}>
                    Builder
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
