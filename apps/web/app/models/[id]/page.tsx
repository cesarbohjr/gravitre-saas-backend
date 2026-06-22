"use client"

import { use, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { mlModelsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, Brain, Rocket, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

const statusStyles: Record<string, string> = {
  draft: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  training: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  validating: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  deployed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  archived: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
}

function formatDate(value?: string | null): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleString()
}

export default function ModelDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { user } = useAuth()
  const [isDeploying, setIsDeploying] = useState(false)

  const { data: model, error, isLoading, mutate, isValidating } = useSWR(
    user ? ["ml-model", id] : null,
    () => mlModelsApi.get(id)
  )

  const canDeploy =
    model &&
    (model.status === "ready" || model.status === "deployed") &&
    model.currentVersion > 0

  async function handleDeploy() {
    if (!model) return
    setIsDeploying(true)
    try {
      await mlModelsApi.deploy(id, model.currentVersion || undefined)
      toast.success("Deployment updated", {
        description: `Version ${model.currentVersion} is now active.`,
      })
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Deploy failed")
    } finally {
      setIsDeploying(false)
    }
  }

  return (
    <AppShell title={model?.name ?? "Model"}>
      <div className="mx-auto max-w-4xl p-4 sm:p-6 space-y-6">
        <Button variant="ghost" size="sm" className="-ml-2 h-8" asChild>
          <Link href="/models">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Model Registry
          </Link>
        </Button>

        {isLoading ? (
          <Skeleton className="h-32 w-full rounded-xl" />
        ) : error ? (
          <WorkSectionErrorCard
            title="Model unavailable"
            message={error instanceof Error ? error.message : "Unknown error"}
            onRetry={() => mutate()}
          />
        ) : model ? (
          <>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Brain className="h-5 w-5 text-muted-foreground" />
                  <h1 className="text-2xl font-semibold tracking-tight">{model.name}</h1>
                  <Badge
                    variant="outline"
                    className={cn("capitalize", statusStyles[model.status] ?? statusStyles.draft)}
                  >
                    {model.status}
                  </Badge>
                </div>
                {model.description ? (
                  <p className="text-sm text-muted-foreground max-w-2xl">{model.description}</p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
                  <RefreshCw className={cn("h-4 w-4 mr-1", isValidating && "animate-spin")} />
                  Refresh
                </Button>
                <Button size="sm" disabled={!canDeploy || isDeploying} onClick={() => void handleDeploy()}>
                  <Rocket className="h-4 w-4 mr-1" />
                  {isDeploying ? "Deploying…" : "Deploy latest version"}
                </Button>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Type</span>
                    <span className="capitalize">{model.modelType.replace(/_/g, " ")}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Current version</span>
                    <span>v{model.currentVersion}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Deployed version</span>
                    <span>{model.deployedVersion != null ? `v${model.deployedVersion}` : "—"}</span>
                  </div>
                  {model.baseModel ? (
                    <div className="flex justify-between gap-2">
                      <span className="text-muted-foreground">Base model</span>
                      <span className="truncate">{model.baseModel}</span>
                    </div>
                  ) : null}
                  {model.datasetId ? (
                    <div className="flex justify-between gap-2">
                      <span className="text-muted-foreground">Dataset</span>
                      <Link href="/training" className="text-primary underline-offset-4 hover:underline truncate">
                        {model.datasetId}
                      </Link>
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">Timeline</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Created</span>
                    <span>{formatDate(model.createdAt)}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Updated</span>
                    <span>{formatDate(model.updatedAt)}</span>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Versions</CardTitle>
              </CardHeader>
              <CardContent>
                {model.versions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No trained versions yet. Start a training job from{" "}
                    <Link href="/training" className="text-primary underline-offset-4 hover:underline">
                      Training
                    </Link>{" "}
                    and link it to this registry entry.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {model.versions.map((version) => (
                      <li
                        key={version.version}
                        className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2 text-sm"
                      >
                        <span className="font-medium">v{version.version}</span>
                        <span className="text-muted-foreground">{formatDate(version.createdAt)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </>
        ) : null}
      </div>
    </AppShell>
  )
}
