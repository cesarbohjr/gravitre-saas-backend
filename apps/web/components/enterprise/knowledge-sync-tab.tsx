"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import { BookOpen, RefreshCw, Play } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { connectorsApi, knowledgeSyncApi } from "@/lib/api"
import type { Connector, KnowledgeSyncJob } from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

const KNOWLEDGE_CONNECTOR_TYPES = new Set(["notion", "confluence", "hubspot", "zendesk"])

function formatRelative(iso: string | null | undefined) {
  if (!iso) return "—"
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

function jobStatusClass(status: string): string {
  if (status === "completed") return "border-success/30 bg-success/10 text-success"
  if (status === "failed") return "border-destructive/30 bg-destructive/10 text-destructive"
  if (status === "running" || status === "queued") return "border-primary/30 bg-primary/10 text-primary"
  return "border-border bg-muted/40 text-muted-foreground"
}

function JobRow({
  job,
  connectorName,
}: {
  job: KnowledgeSyncJob
  connectorName?: string
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border/60 px-3 py-2.5 text-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium text-foreground">{connectorName ?? job.connector_id}</p>
          <Badge variant="outline" className="capitalize">
            {job.source_type}
          </Badge>
          <Badge variant="outline" className={cn("capitalize", jobStatusClass(job.status))}>
            {job.status}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {job.trigger_type} · {formatRelative(job.created_at)}
          {job.pages_synced != null ? ` · ${job.pages_synced} pages` : ""}
          {job.chunks_added != null ? ` · ${job.chunks_added} chunks` : ""}
        </p>
        {job.error_message ? (
          <p className="text-xs text-destructive text-pretty">{job.error_message}</p>
        ) : null}
      </div>
    </div>
  )
}

export function KnowledgeSyncTab({
  isAdmin,
  canTriggerSync,
}: {
  isAdmin: boolean
  canTriggerSync?: boolean
}) {
  const allowSync = canTriggerSync ?? isAdmin
  const allowFullSync = isAdmin
  const [fullSync, setFullSync] = useState(false)
  const [triggeringId, setTriggeringId] = useState<string | null>(null)

  const { data: connectorsData, isLoading: connectorsLoading } = useSWR(
    "connectors-for-knowledge-sync",
    () => connectorsApi.list(),
    { revalidateOnFocus: false },
  )

  const {
    data: jobsData,
    error: jobsError,
    isLoading: jobsLoading,
    mutate: mutateJobs,
  } = useSWR("knowledge-sync-jobs", () => knowledgeSyncApi.listSyncJobs({ limit: 25 }), {
    revalidateOnFocus: false,
  })

  const connectors = connectorsData?.connectors ?? []
  const knowledgeConnectors = useMemo(
    () =>
      connectors.filter(
        (connector: Connector) =>
          connector.status === "active" &&
          KNOWLEDGE_CONNECTOR_TYPES.has(String(connector.type ?? "").toLowerCase()),
      ),
    [connectors],
  )

  const connectorNames = useMemo(() => {
    const map = new Map<string, string>()
    for (const connector of connectors) {
      map.set(connector.id, connector.name)
    }
    return map
  }, [connectors])

  const triggerSync = async (connectorId: string) => {
    if (!allowSync) return
    setTriggeringId(connectorId)
    try {
      await knowledgeSyncApi.triggerConnectorSync(connectorId, {
        fullSync: allowFullSync && fullSync,
      })
      await mutateJobs()
      toast.success("Knowledge sync queued")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed to start")
    } finally {
      setTriggeringId(null)
    }
  }

  if (connectorsLoading || jobsLoading) return <TabSkeleton rows={4} />

  const jobs = jobsData?.jobs ?? []

  return (
    <div className="space-y-4">
      <Alert>
        <BookOpen className="h-4 w-4" aria-hidden />
        <AlertTitle>Knowledge sync</AlertTitle>
        <AlertDescription className="text-pretty">
          Scheduled sync runs via internal cron. Workspace members can queue incremental syncs from
          active knowledge connectors; full re-ingest requires an admin. Connectors must be active with
          sync targets configured (Notion/Confluence) or vendor knowledge sync enabled.
        </AlertDescription>
      </Alert>

      {!allowSync ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <BookOpen className="h-8 w-8 text-muted-foreground" aria-hidden />
            <p className="text-sm text-muted-foreground">
              Viewer role can review sync history but cannot trigger manual syncs.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Manual sync</CardTitle>
            <CardDescription>Queue an immediate knowledge ingest for a connector.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2">
              {allowFullSync ? (
                <>
                  <Switch id="full-sync" checked={fullSync} onCheckedChange={setFullSync} />
                  <Label htmlFor="full-sync" className="text-sm text-muted-foreground">
                    Full sync (re-ingest all targets)
                  </Label>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Incremental sync only (admin required for full sync).</p>
              )}
            </div>
            {knowledgeConnectors.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No active knowledge connectors.{" "}
                <Link href="/connectors" className="text-primary underline-offset-4 hover:underline">
                  Connect Notion, Confluence, HubSpot, or Zendesk
                </Link>
                .
              </p>
            ) : (
              <div className="space-y-2">
                {knowledgeConnectors.map((connector) => (
                  <div
                    key={connector.id}
                    className="flex flex-col gap-2 rounded-lg border border-border/60 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="text-sm font-medium text-foreground">{connector.name}</p>
                      <p className="text-xs capitalize text-muted-foreground">{connector.type}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={triggeringId === connector.id}
                      onClick={() => void triggerSync(connector.id)}
                    >
                      <Play className={cn("mr-1.5 h-3.5 w-3.5", triggeringId === connector.id && "animate-pulse")} />
                      {triggeringId === connector.id ? "Queueing…" : "Run sync"}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div>
            <CardTitle className="text-base">Recent sync jobs</CardTitle>
            <CardDescription>Last 25 knowledge sync jobs for this workspace.</CardDescription>
          </div>
          <Button variant="outline" size="sm" disabled={jobsLoading} onClick={() => void mutateJobs()}>
            <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {jobsError ? (
            <p className="text-sm text-destructive">
              {jobsError instanceof Error ? jobsError.message : "Failed to load sync jobs"}
            </p>
          ) : jobs.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No sync jobs yet.</p>
          ) : (
            jobs.map((job) => (
              <JobRow key={job.id} job={job} connectorName={connectorNames.get(job.connector_id)} />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
