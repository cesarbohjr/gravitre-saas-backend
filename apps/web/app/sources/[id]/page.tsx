"use client"

import { useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { useRouter, useParams } from "next/navigation"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { sourceTypeVendorKey } from "@/lib/brand-vendor"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { SourceQueryPanel } from "@/components/gravitre/source-query-panel"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { formatReportedCount as formatCount, reportedNumber, sourceSyncFeedback } from "@/lib/source-evidence"
import { sourcesApi } from "@/lib/api"
import { buildWorkflowFromSourceUrl } from "@/lib/source-workflow-handoff"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import {
  ArrowLeft,
  RefreshCw,
  Trash2,
  Activity,
  Check,
  AlertCircle,
  ExternalLink,
  Loader2,
} from "lucide-react"
import { NucleoConnector } from "@/components/icons/nucleo/semantic"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

const statusVariants: Record<string, "success" | "warning" | "error" | "info" | "muted"> = {
  connected: "success",
  disconnected: "muted",
  error: "error",
  syncing: "info",
}

function formatRelative(iso: string | undefined): string {
  if (!iso) return "Not reported"
  const timestamp = new Date(iso)
  if (Number.isNaN(timestamp.getTime())) return "Not reported"
  const diffMs = Date.now() - timestamp.getTime()
  const minutes = Math.max(0, Math.floor(diffMs / 60000))
  if (minutes < 1) return "Just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

interface SchemaTable {
  name: string
  schema?: string
  columns?: Array<{ name: string; type: string }>
}

export default function SourceDetailPage() {
  const router = useRouter()
  const params = useParams()
  const sourceId = String(params.id ?? "")
  const { user } = useAuth()
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const mutationLock = useRef(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [testSucceeded, setTestSucceeded] = useState(false)
  const [testMessage, setTestMessage] = useState<string | null>(null)

  const { data, error, isLoading, mutate } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}` : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )
  const { data: schemaData, error: schemaError, isLoading: schemaLoading, mutate: mutateSchema } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}/schema` : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )
  const { data: historyData, error: historyError, isLoading: historyLoading, mutate: mutateHistory } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}/sync-history` : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const source = (data as { source?: Record<string, unknown> } | undefined)?.source
  usePublishGravitreAISelection(source ? { kind: "source", id: sourceId, label: String(source.name ?? "Source") } : null)
  const schemaTables = useMemo(() => {
    const tables = (schemaData as { tables?: SchemaTable[] } | undefined)?.tables
    return Array.isArray(tables) ? tables : []
  }, [schemaData])
  const history = (historyData as { history?: Array<Record<string, unknown>> } | undefined)?.history ?? []

  const suggestions = useMemo(
    () =>
      schemaTables.slice(0, 3).flatMap((table) => [
        `How many rows are in ${table.name}?`,
        `Show 10 sample rows from ${table.name}`,
      ]),
    [schemaTables]
  )

  const handleSync = async () => {
    if (mutationLock.current) return
    mutationLock.current = true
    try {
      setSyncing(true)
      const feedback = sourceSyncFeedback(await sourcesApi.sync(sourceId))
      if (feedback.kind === "error") toast.error(feedback.message)
      else if (feedback.kind === "success") toast.success(feedback.message)
      else toast.message(feedback.message)
      await Promise.allSettled([mutate(), mutateHistory(), mutateSchema()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed")
    } finally {
      mutationLock.current = false
      setSyncing(false)
    }
  }

  const handleTestConnection = async () => {
    if (mutationLock.current) return
    mutationLock.current = true
    try {
      setTestingConnection(true)
      setTestMessage(null)
      setTestSucceeded(false)
      const result = await sourcesApi.testExisting(sourceId)
      setTestSucceeded(result.success === true)
      setTestMessage(result.message ?? (result.success ? "Connection successful" : "Connection failed"))
      if (!result.success) toast.error(result.message ?? "Connection test failed")
    } catch (err) {
      setTestMessage(err instanceof Error ? err.message : "Connection test failed")
      toast.error("Connection test failed")
    } finally {
      mutationLock.current = false
      setTestingConnection(false)
    }
  }

  const handleDelete = async () => {
    if (mutationLock.current) return
    mutationLock.current = true
    setDeleting(true)
    setDeleteError(null)
    try {
      await sourcesApi.delete(sourceId)
      toast.success("Source removed")
      router.push("/sources")
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed")
    } finally {
      mutationLock.current = false
      setDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <AppShell title="Source">
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </AppShell>
    )
  }

  if (!source) {
    return (
      <AppShell title="Source">
        <div className="p-6">
          <button onClick={() => router.push("/sources")} className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <ArrowLeft className="h-4 w-4" /> Back to sources
          </button>
          <WorkSectionErrorCard title="Source unavailable" message={error instanceof Error ? error.message : "This source was not returned."} onRetry={() => void mutate()} />
        </div>
      </AppShell>
    )
  }

  const name = String(source.name ?? "Source")
  const status = String(source.status ?? "Not reported")
  const environment = source.environment === "staging" || source.environment === "production" ? source.environment : null
  const busy = syncing || testingConnection || deleting
  const records = source.recordCount ?? source.record_count
  const lastSync = (source.lastSync ?? source.last_sync ?? source.lastSyncAt) as string | undefined
  const tables = schemaData && Array.isArray((schemaData as { tables?: unknown }).tables) ? schemaTables.length : source.tables ?? source.tablesCount


  return (
    <AppShell title={name}>
      <div data-composition="manage">
        <GravitrePageHeader
          eyebrow="Sources"
          title={name}
          description={String(source.description ?? (source.type ? `${source.type} data source` : "Source lifecycle, grounding and dependent work"))}
          icon={<NucleoConnector className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" size="sm" asChild>
                <Link href="/sources">
                  <ArrowLeft className="mr-1 h-4 w-4" />
                  Back
                </Link>
              </Button>
              <StatusBadge variant={statusVariants[status] ?? "muted"} dot>
                {status}
              </StatusBadge>
              {environment ? <EnvironmentBadge environment={environment} /> : <span className="text-xs text-muted-foreground">Environment not reported</span>}
              <AskGravitreSummonButton label="Explain this source" prompt="Explain this source’s grounding, freshness and dependent work." />
              <Button
                variant="outline"
                size="sm"
                className="h-9 gap-2"
                onClick={() => void handleTestConnection()}
                disabled={busy}
              >
                {testingConnection ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
                Test Connection
              </Button>
              <Button size="sm" className="h-9 gap-2" onClick={() => void handleSync()} disabled={busy}>
                {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Sync Now
              </Button>
            </div>
          }
        >
          <div className="flex items-center gap-3 pt-1">
            <ConnectorIcon
              vendor={sourceTypeVendorKey(String(source.type ?? ""))}
              name={name}
              size="sm"
              showStatusIndicator={false}
            />
            <span className="text-xs text-muted-foreground">{String(source.type ?? "")}</span>
          </div>
        </GravitrePageHeader>

        <div className="space-y-6 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          {error ? <WorkSectionErrorCard title="Source refresh unavailable" message="Showing the last returned source. Retry to refresh its lifecycle and counts." onRetry={() => void mutate()} /> : null}
          <section className="grid grid-cols-1 gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-4">
            <GravitreMetric label="Status" value={status} hint="Connection lifecycle" />
            <GravitreMetric
              label="Tables"
              value={formatCount(tables)}
              hint="From schema when available"
            />
            <GravitreMetric
              label="Records"
              value={formatCount(records)}
              hint="Reported row volume"
            />
            <GravitreMetric
              label="Last sync"
              value={formatRelative(lastSync)}
              hint="Most recent sync"
            />
          </section>

          {testMessage ? (
            <div role="status" className={cn("border-l-2 p-3 text-sm", testSucceeded ? "border-[color:var(--g-brand)] text-[color:var(--g-brand-active)]" : "border-destructive text-destructive")}>
              {testMessage}
            </div>
          ) : null}

          <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Overview</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground font-medium">Connection</p>
                  <p className="text-sm text-foreground mt-1 font-mono">
                    {source.connectionHost
                      ? `${String(source.connectionHost)}:${String(source.connectionPort ?? "")}`
                      : source.connectorId
                      ? `Connector ${String(source.connectorId).slice(0, 8)}…`
                      : "Not reported"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium">Database</p>
                  <p className="text-sm text-foreground mt-1 font-mono">
                    {String(source.connectionDatabase ?? "—")}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium">Last sync</p>
                  <p className="text-sm text-foreground mt-1">{formatRelative(lastSync)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium">Sync frequency</p>
                  <p className="text-sm text-foreground mt-1">
                    {reportedNumber(source.syncIntervalSeconds) == null ? "Not reported" : `Every ${Math.round(Number(source.syncIntervalSeconds) / 60)} minutes`}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium">Tables</p>
                  <p className="text-sm text-foreground mt-1">{formatCount(tables)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium">Total records</p>
                  <p className="text-sm text-foreground mt-1">{formatCount(records)}</p>
                </div>
              </div>
            </div>

            <SourceQueryPanel sourceId={sourceId} suggestions={suggestions} />

            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-foreground">Schema preview</h2>
                <span className="text-xs text-muted-foreground">{formatCount(tables)} tables</span>
              </div>
              {schemaError ? <WorkSectionErrorCard title="Could not refresh schema" onRetry={() => void mutateSchema()} /> : null}
              <AdaptiveDataView className="border-0">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Table</th>
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Schema</th>
                      <th className="text-left py-2 px-3 text-muted-foreground font-medium">Columns</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schemaTables.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-3 py-6 text-center text-muted-foreground">
                          {schemaLoading ? "Loading schema…" : !Array.isArray((schemaData as { tables?: unknown } | undefined)?.tables) ? "Schema not reported" : "No schema tables returned"}
                        </td>
                      </tr>
                    ) : (
                      schemaTables.slice(0, 20).map((table) => (
                        <tr key={`${table.schema ?? "public"}.${table.name}`} className="border-b border-border/50">
                          <td className="py-2 px-3 font-mono text-foreground">{table.name}</td>
                          <td className="py-2 px-3 text-muted-foreground">{table.schema ?? "—"}</td>
                          <td className="py-2 px-3 text-muted-foreground">{table.columns?.length ?? "Not reported"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </AdaptiveDataView>
            </div>

            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Sync history</h2>
              <div className="space-y-2">
                {historyError ? <WorkSectionErrorCard title="Could not refresh sync history" onRetry={() => void mutateHistory()} /> : null}
                {history.length === 0 ? (
                  <p className="text-xs text-muted-foreground">{historyLoading ? "Loading sync history…" : !Array.isArray((historyData as { history?: unknown } | undefined)?.history) ? "Sync history not reported" : "No sync history returned."}</p>
                ) : (
                  history.map((item) => {
                    const ok = String(item.status) === "success"
                    return (
                      <div key={String(item.id)} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                        <div className="flex items-center gap-3">
                          {ok ? (
                            <Check className="h-4 w-4 text-emerald-500" />
                          ) : (
                            <AlertCircle className="h-4 w-4 text-destructive" />
                          )}
                          <div>
                            <p className="text-xs text-foreground">
                              {ok
                                ? `Synced ${formatCount(item.records)} records across ${formatCount(item.tables)} tables`
                                : String(item.error ?? "Sync failed")}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {formatRelative(String(item.createdAt ?? ""))} · {String(item.trigger ?? "manual")}
                            </p>
                          </div>
                        </div>
                        {reportedNumber(item.durationMs) != null ? (
                          <span className="text-xs text-muted-foreground">{Math.round(Number(item.durationMs) / 1000)}s</span>
                        ) : null}
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Quick stats</h2>
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Created</span>
                  <span className="text-foreground">{formatRelative(String(source.createdAt ?? ""))}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Type ID</span>
                  <span className="font-mono text-foreground">{String(source.typeId ?? "—")}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Tables</span>
                  <span className="text-foreground">{formatCount(tables)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Records</span>
                  <span className="text-foreground">{formatCount(records)}</span>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Actions</h2>
              <div className="space-y-2">
                <Button variant="outline" size="sm" className="w-full h-9 justify-start gap-2" asChild>
                  <Link
                    href={buildWorkflowFromSourceUrl({
                      id: String(source.id),
                      name,
                      type: String(source.type ?? ""),
                      connectorId: source.connectorId ? String(source.connectorId) : undefined,
                    })}
                  >
                    <ExternalLink className="h-4 w-4" />
                    Use in new Workflow
                  </Link>
                </Button>
                {source.connectorId ? (
                  <Button variant="outline" size="sm" className="w-full h-9 justify-start gap-2" asChild>
                    <Link href={`/connectors/${String(source.connectorId)}`}>
                      <ExternalLink className="h-4 w-4" />
                      Open linked Connector
                    </Link>
                  </Button>
                ) : null}
                <Button
                  variant="outline"
                  size="sm"
                  className={cn(
                    "w-full h-9 justify-start gap-2 text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/30"
                  )}
                  onClick={() => setDeleteModalOpen(true)}
                >
                  <Trash2 className="h-4 w-4" />
                  Remove source
                </Button>
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>

      <Dialog open={deleteModalOpen} onOpenChange={(open) => { if (!deleting) setDeleteModalOpen(open) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove source</DialogTitle>
            <DialogDescription>
              This will disconnect {name} from Gravitre. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {deleteError ? <p role="alert" className="text-sm text-destructive">{deleteError}</p> : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" disabled={deleting} onClick={() => setDeleteModalOpen(false)}>Cancel</Button>
            <Button variant="destructive" disabled={busy} onClick={() => void handleDelete()}>{deleting ? "Removing…" : "Remove source"}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
