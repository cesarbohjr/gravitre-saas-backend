"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { useRouter, useParams } from "next/navigation"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { sourceTypeVendorKey } from "@/lib/brand-vendor"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { SourceQueryPanel } from "@/components/gravitre/source-query-panel"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { sourcesApi } from "@/lib/api"
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
  if (!iso) return "Never"
  const timestamp = new Date(iso)
  if (Number.isNaN(timestamp.getTime())) return "Never"
  const diffMs = Date.now() - timestamp.getTime()
  const minutes = Math.max(0, Math.floor(diffMs / 60000))
  if (minutes < 1) return "Just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function formatCount(value: number | undefined): string {
  if (!value) return "0"
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
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
  const [testMessage, setTestMessage] = useState<string | null>(null)

  const { data, error, isLoading, mutate } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}` : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )
  const { data: schemaData } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}/schema` : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )
  const { data: historyData, mutate: mutateHistory } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}/sync-history` : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const source = (data as { source?: Record<string, unknown> } | undefined)?.source
  const schemaTables = ((schemaData as { tables?: SchemaTable[] } | undefined)?.tables ?? []) as SchemaTable[]
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
    try {
      setSyncing(true)
      await sourcesApi.sync(sourceId)
      toast.success("Sync completed")
      await Promise.all([mutate(), mutateHistory()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed")
    } finally {
      setSyncing(false)
    }
  }

  const handleTestConnection = async () => {
    try {
      setTestingConnection(true)
      setTestMessage(null)
      const result = await sourcesApi.testExisting(sourceId)
      setTestMessage(result.message ?? (result.success ? "Connection successful" : "Connection failed"))
      if (!result.success) toast.error(result.message ?? "Connection test failed")
    } catch (err) {
      setTestMessage(err instanceof Error ? err.message : "Connection test failed")
      toast.error("Connection test failed")
    } finally {
      setTestingConnection(false)
    }
  }

  const handleDelete = async () => {
    try {
      await sourcesApi.delete(sourceId)
      toast.success("Source removed")
      router.push("/sources")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed")
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

  if (error || !source) {
    return (
      <AppShell title="Source">
        <div className="p-6">
          <button onClick={() => router.push("/sources")} className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <ArrowLeft className="h-4 w-4" /> Back to Sources
          </button>
          <p className="text-sm text-red-400">{error instanceof Error ? error.message : "Source not found"}</p>
        </div>
      </AppShell>
    )
  }

  const name = String(source.name ?? "Source")
  const status = String(source.status ?? "connected")
  const environment = (String(source.environment ?? "production") === "staging" ? "staging" : "production") as
    | "production"
    | "staging"

  return (
    <AppShell title={name}>
      <div className="p-6">
        <button
          onClick={() => router.push("/sources")}
          className="mb-4 flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Sources
        </button>

        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <ConnectorIcon
              vendor={sourceTypeVendorKey(String(source.type ?? ""))}
              name={name}
              size="md"
              showStatusIndicator={false}
            />
            <div>
              <h1 className="text-2xl font-semibold text-foreground">{name}</h1>
              <p className="text-sm text-muted-foreground mt-1">
                {String(source.description ?? `${source.type} data source`)}
              </p>
              <div className="flex items-center gap-2 mt-3">
                <StatusBadge variant={statusVariants[status] ?? "muted"} dot>
                  {status}
                </StatusBadge>
                <EnvironmentBadge environment={environment} />
                <span className="text-xs text-muted-foreground">{String(source.type ?? "")}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-9 gap-2" onClick={() => void handleTestConnection()} disabled={testingConnection}>
              {testingConnection ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
              Test Connection
            </Button>
            <Button size="sm" className="h-9 gap-2 bg-emerald-600 hover:bg-emerald-700" onClick={() => void handleSync()} disabled={syncing}>
              {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Sync Now
            </Button>
          </div>
        </div>

        {testMessage ? (
          <div className="mb-6 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-400">
            {testMessage}
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Overview</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Connection</p>
                  <p className="text-sm text-foreground mt-1 font-mono">
                    {source.connectionHost
                      ? `${String(source.connectionHost)}:${String(source.connectionPort ?? "")}`
                      : source.connectorId
                      ? `Connector ${String(source.connectorId).slice(0, 8)}…`
                      : "Configured"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Database</p>
                  <p className="text-sm text-foreground mt-1 font-mono">
                    {String(source.connectionDatabase ?? "—")}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Last Sync</p>
                  <p className="text-sm text-foreground mt-1">{formatRelative(String(source.lastSyncAt ?? ""))}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Sync Frequency</p>
                  <p className="text-sm text-foreground mt-1">
                    Every {Math.round(Number(source.syncIntervalSeconds ?? 300) / 60)} minutes
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Tables</p>
                  <p className="text-sm text-foreground mt-1">{Number(source.tablesCount ?? 0)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Total Records</p>
                  <p className="text-sm text-foreground mt-1">{formatCount(Number(source.recordCount ?? 0))}</p>
                </div>
              </div>
            </div>

            <SourceQueryPanel sourceId={sourceId} suggestions={suggestions} />

            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-foreground">Schema Preview</h2>
                <span className="text-xs text-muted-foreground">{schemaTables.length} tables</span>
              </div>
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
                          Run sync to discover schema
                        </td>
                      </tr>
                    ) : (
                      schemaTables.slice(0, 20).map((table) => (
                        <tr key={`${table.schema ?? "public"}.${table.name}`} className="border-b border-border/50">
                          <td className="py-2 px-3 font-mono text-foreground">{table.name}</td>
                          <td className="py-2 px-3 text-muted-foreground">{table.schema ?? "—"}</td>
                          <td className="py-2 px-3 text-muted-foreground">{table.columns?.length ?? 0}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </AdaptiveDataView>
            </div>

            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Sync History</h2>
              <div className="space-y-2">
                {history.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No sync history yet.</p>
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
                                ? `Synced ${formatCount(Number(item.records ?? 0))} records across ${Number(item.tables ?? 0)} tables`
                                : String(item.error ?? "Sync failed")}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {formatRelative(String(item.createdAt ?? ""))} · {String(item.trigger ?? "manual")}
                            </p>
                          </div>
                        </div>
                        {item.durationMs ? (
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
              <h2 className="text-sm font-semibold text-foreground mb-4">Quick Stats</h2>
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
                  <span className="text-foreground">{Number(source.tablesCount ?? 0)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Records</span>
                  <span className="text-foreground">{formatCount(Number(source.recordCount ?? 0))}</span>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4">Actions</h2>
              <div className="space-y-2">
                <Button variant="outline" size="sm" className="w-full h-9 justify-start gap-2" asChild>
                  <Link href="/workflows/new">
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
                  Remove Source
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Source</DialogTitle>
            <DialogDescription>
              This will disconnect {name} from Gravitre. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteModalOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={() => void handleDelete()}>Remove Source</Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
