"use client"

import { useState, useMemo } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { ConnectorLinkage } from "@/components/connectors/connector-linkage"
import { KnowledgeSyncButton } from "@/components/connectors/knowledge-sync-button"
import { NucleoConnector } from "@/components/icons/nucleo/semantic"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { lookupConnectorCategory, resolveConnectorDisplayStatus } from "@/lib/connectors"
import { connectorsApi } from "@/lib/api"
import type { Connector, Workflow, WorkflowListResponse } from "@/types/api"
import type { VendorActionCatalog, ConnectorActionCatalogResponse } from "@/lib/connector-actions"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"
import {
  ArrowLeft,
  XCircle,
  RefreshCw,
  Settings,
  Trash2,
  Eye,
  EyeOff,
  Copy,
  Check,
  MoreVertical,
  Download,
  Key,
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
  usePublishGravitreAISelection(
    connector ? { kind: "connector", id: connector.id, label: connector.name } : null,
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
      <div className="flex min-h-full flex-col" data-testid="connector-detail-b">
        <GravitrePageHeader
          eyebrow="Connectors"
          title={connector.name}
          description={connector.description}
          icon={<NucleoConnector className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <AskGravitreSummonButton />
              <Button variant="ghost" size="sm" asChild>
                <Link href="/connectors">
                  <ArrowLeft className="mr-1 h-4 w-4" />
                  Back
                </Link>
              </Button>
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
                    Export logs
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive"
                    onClick={() => setShowDeleteDialog(true)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Remove connector
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          }
        >
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <ConnectorIcon
              vendor={connector.type}
              status={isSyncing ? "syncing" : connector.status === "connected" ? "connected" : connector.status === "error" ? "error" : "disconnected"}
              size="sm"
              showStatusIndicator
            />
            <span
              className={cn(
                "text-[10px] px-2 py-0.5 rounded-full font-medium",
                connector.environment === "production"
                  ? "bg-success/10 text-success"
                  : "bg-warning/10 text-warning",
              )}
            >
              {connector.environment}
            </span>
            <span className="text-xs text-muted-foreground">{connector.type}</span>
            <span className="text-border text-xs">|</span>
            <span className="text-xs text-muted-foreground">{connector.category}</span>
            <span className="text-border text-xs">|</span>
            <span className="text-xs text-muted-foreground">Created {connector.createdAt}</span>
          </div>
        </GravitrePageHeader>

        <div className="flex-1 space-y-6 overflow-auto p-4 md:p-6">
          <section data-testid="connector-detail-status" className="border-b border-divide pb-4">
            <p className={TYPE.eyebrow}>Live status</p>
            <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-4">
            <div>
              <dt className="text-xs text-muted-foreground">Status</dt>
              <dd className="text-sm font-medium capitalize text-foreground">{connector.status}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Last sync</dt>
              <dd className="text-sm font-medium text-foreground">{connector.lastSync}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Sync interval</dt>
              <dd className="text-sm font-medium text-foreground">{connector.config.syncInterval}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Environment</dt>
              <dd className="text-sm font-medium capitalize text-foreground">{connector.environment}</dd>
            </div>
            </dl>
            <p className={cn(TYPE.meta, "mt-3")}>
              Usage metrics and activity logs are not recorded for this connector.
            </p>
          </section>

          <section data-testid="connector-detail-linkage" className="border-b border-divide pb-4">
            <p className={TYPE.eyebrow}>Linkage & actions</p>
            <div className="mt-2">
              <ConnectorLinkage
                vendor={vendorKey}
                connectorStatus={connector.status}
                catalog={vendorCatalog}
                workflows={workflows}
              />
            </div>
          </section>

          <section data-testid="connector-detail-config" className="space-y-3 border-b border-divide py-4">
            <p className={TYPE.eyebrow}>Configuration</p>
            <h2 className="flex items-center gap-2 text-sm font-medium">
              <Key className="h-4 w-4 text-warning" />
              Credentials & sync
            </h2>
                <div className="space-y-1.5">
                  <label className="text-xs text-muted-foreground font-medium">API Key</label>
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
                  <label className="text-xs text-muted-foreground font-medium">Webhook URL</label>
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
                  <label className="text-xs text-muted-foreground font-medium">Sync interval</label>
                <p className="text-sm font-medium">Every {connector.config.syncInterval}</p>
              </div>
          </section>
        </div>

        {/* Delete Dialog */}
        <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-destructive">
                <Trash2 className="h-5 w-5" />
                Remove connector
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
                Remove connector
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
                <label className="text-sm font-medium">Sync interval</label>
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
                Save changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
