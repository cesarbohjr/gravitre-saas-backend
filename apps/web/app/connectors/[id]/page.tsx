"use client"

import { useState, useMemo } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { ConnectorLinkage } from "@/components/connectors/connector-linkage"
import { KnowledgeSyncButton } from "@/components/connectors/knowledge-sync-button"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { lookupConnectorCategory, resolveConnectorDisplayStatus } from "@/lib/connectors"
import { connectorsApi } from "@/lib/api"
import type { Connector, Workflow, WorkflowListResponse } from "@/types/api"
import type { VendorActionCatalog, ConnectorActionCatalogResponse } from "@/lib/connector-actions"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Loader2,
  WifiOff,
  RefreshCw,
  Settings,
  Trash2,
  Clock,
  Eye,
  EyeOff,
  Copy,
  Check,
  MoreVertical,
  Download,
  Key,
  Globe,
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

const statusConfig = {
  connected: { color: "text-success", bg: "bg-emerald-500", icon: CheckCircle2, label: "Connected" },
  disconnected: { color: "text-zinc-500", bg: "bg-zinc-500", icon: WifiOff, label: "Disconnected" },
  error: { color: "text-destructive", bg: "bg-red-500", icon: XCircle, label: "Error" },
  syncing: { color: "text-blue-500", bg: "bg-blue-500", icon: Loader2, label: "Syncing" },
}

function formatConfigValue(config: Record<string, unknown> | undefined, key: string): string {
  const value = config?.[key]
  return typeof value === "string" && value.trim() ? value : ""
}

function unwrapConnectorPayload(payload: unknown): Record<string, unknown> | null {
  if (!payload || typeof payload !== "object") return null
  const record = payload as Record<string, unknown>
  if (record.connector && typeof record.connector === "object") {
    return record.connector as Record<string, unknown>
  }
  return record
}

function mapConnectorRecord(live: Connector | Record<string, unknown>) {
  const raw = unwrapConnectorPayload(live) ?? (live as Record<string, unknown>)
  const vendor = String(raw.type || raw.vendor || "")
  const config = (raw.config as Record<string, unknown> | undefined) ?? {}
  const statusRaw = String(raw.status || "disconnected")
  const authStatus = String(raw.authStatus ?? raw.auth_status ?? "")
  const displayStatus = String(raw.displayStatus ?? raw.display_status ?? "")
  const normalizedStatus = resolveConnectorDisplayStatus(statusRaw, authStatus, displayStatus)
  const lastSyncRaw = raw.lastSync ?? raw.last_sync_at
  return {
    id: String(raw.id || ""),
    name: String(raw.name || vendor || "Connector"),
    type: vendor,
    status: normalizedStatus,
    environment: raw.environment === "staging" ? ("staging" as const) : ("production" as const),
    lastSync: lastSyncRaw ? new Date(String(lastSyncRaw)).toLocaleString() : "—",
    description: String(raw.description || `${vendor} integration`),
    category: lookupConnectorCategory(vendor) ?? "Integration",
    createdAt: String(raw.createdAt ?? raw.created_at ?? "—").slice(0, 10),
    config: {
      apiKey: formatConfigValue(config, "apiKey"),
      webhookUrl: formatConfigValue(config, "webhookUrl"),
      syncInterval: String(
        (raw.syncFrequency ?? raw.sync_frequency ?? formatConfigValue(config, "syncInterval")) || "—",
      ),
    },
  }
}

export default function ConnectorDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { user } = useAuth()
  const connectorId = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : ""

  // G4: live connector record (the page previously hardcoded Salesforce regardless of id).
  const { data: liveConnector, error: connectorError, isLoading: connectorLoading } = useSWR<Connector | Record<string, unknown>>(
    user && connectorId ? `/api/connectors/${connectorId}` : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )

  // G4: action catalog + workflows so we can show real readiness and linkage.
  const { data: catalogData } = useSWR<ConnectorActionCatalogResponse>(
    user && liveConnector ? "/api/connectors/catalog/actions" : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const { data: workflowsData } = useSWR<WorkflowListResponse>(
    user && liveConnector ? "/api/workflows" : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )

  const connector = useMemo(
    () => (liveConnector ? mapConnectorRecord(liveConnector) : null),
    [liveConnector],
  )

  const [showApiKey, setShowApiKey] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)

  if (!user || connectorLoading || !connector) {
    return (
      <AppShell title="Connector">
        <div className="flex flex-col items-center justify-center py-24">
          {!user || connectorLoading ? (
            <>
              <Spinner size="lg" className="mb-4" />
              <p className="text-sm text-muted-foreground">Loading connector…</p>
            </>
          ) : (
            <>
              <XCircle className="h-10 w-10 text-destructive mb-4" />
              <h2 className="text-base font-medium text-foreground mb-1">Connector not found</h2>
              <p className="text-sm text-muted-foreground mb-4">
                {connectorError instanceof Error ? connectorError.message : "This connector may have been removed."}
              </p>
              <Button asChild variant="outline">
                <Link href="/connectors">Back to connectors</Link>
              </Button>
            </>
          )}
        </div>
      </AppShell>
    )
  }

  // Resolve the vendor key the catalog is indexed by.
  const vendorKey = String(
    (liveConnector as Connector | undefined)?.vendor
      ?? (liveConnector as Connector | undefined)?.type
      ?? connector.type
      ?? "",
  ).toLowerCase()
  const vendorCatalog: VendorActionCatalog | null =
    catalogData?.vendors.find((v) => v.vendor.toLowerCase() === vendorKey) ?? null
  const workflows: Workflow[] = workflowsData?.workflows ?? []

  const config = statusConfig[connector.status as keyof typeof statusConfig] ?? statusConfig.disconnected
  const StatusIcon = config.icon

  const handleSync = async () => {
    setIsSyncing(true)
    try {
      await connectorsApi.sync(connectorId)
      toast.success("Sync initiated")
    } catch (err) {
      toast.error("Sync failed", {
        description: err instanceof Error ? err.message : "Please try again",
      })
    } finally {
      setIsSyncing(false)
    }
  }

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    toast.success(`${label} copied to clipboard`)
    setTimeout(() => setCopied(null), 2000)
  }

  const handleDelete = () => {
    toast.success("Connector removed", { description: `${connector.name} has been disconnected` })
    router.push("/connectors")
  }

  return (
    <AppShell title={connector.name} breadcrumbVendor={connector.type}>
      <div className="flex flex-col min-h-full">
        {/* Header */}
        <div className="border-b border-border px-4 md:px-6 py-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="flex items-start gap-4">
              <Link 
                href="/connectors" 
                className="mt-1 p-1.5 rounded-md hover:bg-secondary transition-colors"
              >
                <ArrowLeft className="h-5 w-5 text-muted-foreground" />
              </Link>
              <div className="flex items-center gap-4">
                <ConnectorIcon 
                  vendor={connector.type}
                  status={isSyncing ? "syncing" : connector.status === "connected" ? "connected" : connector.status === "error" ? "error" : "disconnected"}
                  size="md"
                  showStatusIndicator
                />
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-xl font-semibold text-foreground">{connector.name}</h1>
                    <span className={cn(
                      "text-[10px] px-2 py-0.5 rounded-full font-medium",
                      connector.environment === "production" 
                        ? "bg-success/10 text-success" 
                        : "bg-warning/10 text-warning"
                    )}>
                      {connector.environment}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{connector.description}</p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{connector.type}</span>
                    <span className="text-border">|</span>
                    <span>{connector.category}</span>
                    <span className="text-border">|</span>
                    <span>Created {connector.createdAt}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <KnowledgeSyncButton
                connectorId={connectorId}
                connectorType={String(
                  (liveConnector as Connector | undefined)?.type
                    ?? (liveConnector as Connector | undefined)?.vendor
                    ?? connector.type,
                )}
                connectorStatus={String(
                  (liveConnector as Connector | undefined)?.status ?? connector.status,
                )}
              />
              <Button 
                variant="outline" 
                size="sm" 
                className="gap-2"
                onClick={handleSync}
                disabled={isSyncing || connector.status !== "connected"}
              >
                <RefreshCw className={cn("h-4 w-4", isSyncing && "animate-spin")} />
                {isSyncing ? "Syncing..." : "Sync Now"}
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                className="gap-2"
                onClick={() => setShowConfigDialog(true)}
              >
                <Settings className="h-4 w-4" />
                Configure
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 w-8 p-0">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem>
                    <Download className="h-4 w-4 mr-2" />
                    Export Logs
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem 
                    className="text-destructive"
                    onClick={() => setShowDeleteDialog(true)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Remove Connector
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 p-4 md:p-6 space-y-6 overflow-auto">
          {/* Stats Overview */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Status</p>
                    <p className="text-lg font-bold text-foreground capitalize">{connector.status}</p>
                  </div>
                  <div className={cn("h-10 w-10 rounded-full flex items-center justify-center", config.bg + "/10")}>
                    <StatusIcon className={cn("h-5 w-5", config.color, connector.status === "syncing" && "animate-spin")} />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Last Sync</p>
                    <p className="text-sm font-semibold text-foreground">{connector.lastSync}</p>
                  </div>
                  <div className="h-10 w-10 rounded-full flex items-center justify-center bg-blue-500/10">
                    <Clock className="h-5 w-5 text-blue-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Sync Interval</p>
                    <p className="text-sm font-semibold text-foreground">{connector.config.syncInterval}</p>
                  </div>
                  <div className="h-10 w-10 rounded-full flex items-center justify-center bg-violet-500/10">
                    <RefreshCw className="h-5 w-5 text-violet-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Environment</p>
                    <p className="text-sm font-semibold text-foreground capitalize">{connector.environment}</p>
                  </div>
                  <div className="h-10 w-10 rounded-full flex items-center justify-center bg-warning/10">
                    <Globe className="h-5 w-5 text-warning" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Usage metrics — available when observability is wired for this connector */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Usage metrics</CardTitle>
              <CardDescription className="text-xs">
                Request volume and latency charts will appear here once connector telemetry is enabled for your organization.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-border/70 bg-muted/20 text-sm text-muted-foreground">
                No telemetry data yet
              </div>
            </CardContent>
          </Card>

          {/* G4: live action readiness, workflow linkage, and starter workflows */}
          <ConnectorLinkage
            vendor={vendorKey}
            connectorStatus={connector.status}
            catalog={vendorCatalog}
            workflows={workflows}
          />

          {/* Configuration */}
          <div className="grid gap-6">
            {/* Configuration */}
            <Card className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Key className="h-4 w-4 text-warning" />
                  Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground">API Key</label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-secondary px-2 py-1.5 rounded font-mono truncate">
                      {connector.config.apiKey
                        ? showApiKey
                          ? connector.config.apiKey
                          : "••••••••••••••••"
                        : "Not configured"}
                    </code>
                    {connector.config.apiKey ? (
                      <>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-7 w-7 p-0"
                          onClick={() => setShowApiKey(!showApiKey)}
                        >
                          {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-7 w-7 p-0"
                          onClick={() => handleCopy(connector.config.apiKey, "API Key")}
                        >
                          {copied === "API Key" ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                        </Button>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Webhook URL</label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-secondary px-2 py-1.5 rounded font-mono truncate">
                      {connector.config.webhookUrl || "Not configured"}
                    </code>
                    {connector.config.webhookUrl ? (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-7 w-7 p-0"
                        onClick={() => handleCopy(connector.config.webhookUrl, "Webhook URL")}
                      >
                        {copied === "Webhook URL" ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Sync Interval</label>
                  <p className="text-sm font-medium">Every {connector.config.syncInterval}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Activity Logs */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">Activity Logs</CardTitle>
                <Button variant="ghost" size="sm" className="text-xs gap-1.5">
                  <Download className="h-3.5 w-3.5" />
                  Export
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-border/70 bg-muted/20 text-sm text-muted-foreground">
                No activity logs recorded yet
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Delete Dialog */}
        <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <Trash2 className="h-5 w-5" />
                Remove Connector
              </DialogTitle>
              <DialogDescription>
                This will disconnect {connector.name} and remove all associated configurations. 
                This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50 border border-border">
                <ConnectorIcon vendor={connector.type} size="sm" />
                <div>
                  <p className="text-sm font-medium">{connector.name}</p>
                  <p className="text-xs text-muted-foreground">{connector.type} - {connector.environment}</p>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>Cancel</Button>
              <Button variant="destructive" onClick={handleDelete} className="gap-2">
                <Trash2 className="h-4 w-4" />
                Remove Connector
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Configure Dialog */}
        <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <div className="flex items-center gap-3">
                <ConnectorIcon vendor={connector.type} size="md" />
                <div>
                  <DialogTitle>{connector.name}</DialogTitle>
                  <DialogDescription>Update connector configuration</DialogDescription>
                </div>
              </div>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">API Key</label>
                <div className="relative">
                  <Input 
                    type={showApiKey ? "text" : "password"} 
                    defaultValue={connector.config.apiKey}
                    className="pr-10 bg-secondary"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Sync Interval</label>
                <select 
                  defaultValue={connector.config.syncInterval}
                  className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm"
                >
                  <option value="1m">Every 1 minute</option>
                  <option value="5m">Every 5 minutes</option>
                  <option value="15m">Every 15 minutes</option>
                  <option value="30m">Every 30 minutes</option>
                  <option value="1h">Every 1 hour</option>
                </select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowConfigDialog(false)}>Cancel</Button>
              <Button onClick={() => {
                setShowConfigDialog(false)
                toast.success("Configuration updated")
              }}>
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
