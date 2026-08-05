"use client"

// Connectors Page - Integration Hub with Network Topology View
import { Suspense, startTransition, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { ConnectorIcon, ConnectorIconGrid } from "@/components/gravitre/connector-icon"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { ConnectorRecommendations } from "@/components/connectors/connector-recommendations"
import { AvailableConnectorsStrip } from "@/components/connectors/available-connectors-strip"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"
import { 
  Plus, 
  Search,
  RefreshCw,
  Settings,
  Trash2,
  ExternalLink,
  Zap,
  Activity,
  ArrowRight,
  Circle,
  CheckCircle2,
  XCircle,
  Loader2,
  MoreVertical,
  Eye,
  EyeOff,
  AlertTriangle,
  Wifi,
  WifiOff,
  Cable,
  Bot,
  Workflow,
  Filter,
  LayoutGrid,
  List,
  Globe,
  Key,
  Link2,
  Copy,
  Check,
  Receipt,
  Code2,
  ShieldCheck,
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
import { cn } from "@/lib/utils"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { fetcher as apiFetcher, formatUnknownError } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ensureSelectedOrg, getQuickOrgId } from "@/lib/org-context"
import {
  getSelectedEnvironmentFromStorage,
  setSelectedEnvironmentInStorage,
  type AppEnvironment,
} from "@/lib/environment-context"
import { connectorsApi, ApiRequestError } from "@/lib/api"
import { publicApiUrl } from "@/lib/public-urls"
import {
  CONNECTOR_CATEGORIES,
  OAUTH_CONNECTOR_TYPE_SET,
  OAUTH_VENDOR_KEYS,
  PKCE_OAUTH_VENDOR_KEYS,
  connectorVendorKey,
  formatVendorLabel,
  isPartnerGatedConnector,
  shouldShowConnectedConnectorOnHub,
  isPlaidLinkConnector,
  isShippedConnector,
  listAvailableConnectors,
  lookupConnectorCategory,
  resolveConnectorDisplayStatus,
  supportsDualPatAuth,
} from "@/lib/connectors"
import { openPlaidLink } from "@/lib/plaid-link"
import type { Connector as ApiConnector, ConnectorStatus } from "@/types/api"

interface ConnectorAvailability {
  configured: boolean
  authenticated: boolean
  tokenValid: boolean
  scopesValid: boolean
  healthy: boolean
  executable: boolean
  blockingReason?: string
  recoveryAction?: string
  lastCheckedAt?: string
  sourceOfTruth?: string
  requirementNote?: string
  discoveryLimitation?: string
  capabilityNotes?: string[]
}

interface Connector {
  id: string
  name: string
  type: string
  vendorKey: string
  rawStatus?: string
  status: "connected" | "disconnected" | "error" | "syncing"
  displayStatus?: string
  environment: "production" | "staging"
  lastSync: string
  health: number
  description: string
  dataFlowRate?: string
  requestsToday?: number
  latency?: number
  category?: string
  authType?: "oauth" | "apiKey" | "webhook"
  authStatus?: string
  blockingReason?: string
  recoveryAction?: string
  availability?: ConnectorAvailability
  usedByWorkflows?: number
  triggeredByAgents?: number
  config?: {
    apiKey?: string
    webhookUrl?: string
    syncInterval?: string
    subdomain?: string
    instance_url?: string
    owner?: string
    repo?: string
    staged?: boolean
    needs_connection?: boolean
  }
}

function formatLastSync(value: unknown): string {
  if (!value) return "Never"
  const raw = String(value)
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw

  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return "Just now"
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`
  return `${Math.floor(seconds / 86400)} days ago`
}

function parseConnectorAvailability(model: Record<string, unknown>): ConnectorAvailability | undefined {
  const raw =
    model.availability && typeof model.availability === "object"
      ? (model.availability as Record<string, unknown>)
      : null
  if (!raw) return undefined
  return {
    configured: Boolean(raw.configured),
    authenticated: Boolean(raw.authenticated),
    tokenValid: Boolean(raw.tokenValid ?? raw.token_valid),
    scopesValid: Boolean(raw.scopesValid ?? raw.scopes_valid),
    healthy: Boolean(raw.healthy),
    executable: Boolean(raw.executable ?? raw.execution_available),
    blockingReason: String(raw.blockingReason ?? raw.blocking_reason ?? "").trim() || undefined,
    recoveryAction: String(raw.recoveryAction ?? raw.recovery_action ?? "").trim() || undefined,
    lastCheckedAt: String(raw.lastCheckedAt ?? raw.last_checked_at ?? "").trim() || undefined,
    sourceOfTruth: String(raw.sourceOfTruth ?? raw.source_of_truth ?? "").trim() || undefined,
    requirementNote: String(raw.requirementNote ?? raw.requirement_note ?? "").trim() || undefined,
    discoveryLimitation:
      String(raw.discoveryLimitation ?? raw.discovery_limitation ?? "").trim() || undefined,
    capabilityNotes: Array.isArray(raw.capabilityNotes)
      ? (raw.capabilityNotes as unknown[]).map(String)
      : Array.isArray(raw.capability_notes)
        ? (raw.capability_notes as unknown[]).map(String)
        : undefined,
  }
}

function connectorIsExecutable(connector: Connector): boolean {
  if (connector.availability) return connector.availability.executable
  return connector.status === "connected" || connector.status === "syncing"
}

function ConnectorReadinessBadges({ availability }: { availability?: ConnectorAvailability }) {
  if (!availability) return null
  const badges = [
    { label: "Configured", ok: availability.configured },
    { label: "Authenticated", ok: availability.authenticated },
    { label: "Healthy", ok: availability.healthy },
    { label: "Executable", ok: availability.executable },
  ]
  return (
    <div className="flex flex-wrap gap-1 mb-3">
      {badges.map(({ label, ok }) => (
        <span
          key={label}
          className={cn(
            "text-[9px] px-1.5 py-0.5 rounded border font-medium",
            ok
              ? "bg-success/10 text-success border-success/20"
              : "bg-muted text-muted-foreground border-border/70",
          )}
        >
          {label}
        </span>
      ))}
    </div>
  )
}

function connectorNeedsOAuthReconnect(connector: Connector): boolean {
  if (connector.authType !== "oauth") return false
  if (connector.status === "disconnected") return true
  return connector.status === "error" && connector.authStatus === "auth_expired"
}

function connectorStatusLabel(connector: Connector): string {
  if (connector.status === "syncing") return statusConfig.syncing.label
  if (connector.blockingReason === "token_expired" || connector.authStatus === "auth_expired") {
    return "Reconnect required"
  }
  if (connector.blockingReason === "missing_scope") return "Missing OAuth scopes"
  if (connector.blockingReason === "unsupported_action") return "Action unsupported"
  if (connector.blockingReason === "pending_auth" || connector.authStatus === "pending_auth") {
    return "Authentication required"
  }
  if (connector.authStatus === "misconfigured" || connector.blockingReason === "misconfigured") {
    return "Setup required"
  }
  if (connector.availability?.executable) return "Connected and executable"
  if (connector.availability?.healthy && !connector.availability.executable) return "Connected, not executable"
  return statusConfig[connector.status]?.label ?? statusConfig.disconnected.label
}

function normalizeConnector(input: Record<string, unknown> | ApiConnector): Connector {
  const model = input as Record<string, unknown>
  const rawStatus = String(model.status ?? "disconnected")
  const environment = String(input.environment ?? "staging")
  const cfg =
    model.config && typeof model.config === "object"
      ? (model.config as Record<string, unknown>)
      : {}
  const rawVendor = String(model.vendor ?? model.type ?? "").trim()
  const normalizedVendorKey = rawVendor
    ? connectorVendorKey(rawVendor)
    : ""
  const inferredOAuth =
    OAUTH_VENDOR_KEYS.has(normalizedVendorKey) ||
    (rawVendor ? OAUTH_VENDOR_KEYS.has(connectorVendorKey(rawVendor)) : false)
  const authTypeRaw = String(cfg.authType ?? model.authType ?? model.auth_type ?? "")
  const authType =
    authTypeRaw === "oauth" || authTypeRaw === "webhook"
      ? authTypeRaw
      : inferredOAuth
        ? "oauth"
        : "apiKey"
  const authStatus = String(model.authStatus ?? model.auth_status ?? "")
  const displayStatus = String(model.displayStatus ?? model.display_status ?? "")
  const availability = parseConnectorAvailability(model)
  const vendor = rawVendor || "unknown"
  const normalizedStatus = resolveConnectorDisplayStatus(rawStatus, authStatus, displayStatus)
  return {
    id: String(model.id ?? ""),
    name: String(model.name ?? "connector"),
    type: formatVendorLabel(vendor),
    vendorKey: normalizedVendorKey,
    rawStatus,
    status: normalizedStatus,
    displayStatus: displayStatus || undefined,
    environment: environment === "production" ? "production" : "staging",
    lastSync: formatLastSync(model.lastSync ?? model.last_sync ?? model.last_sync_at),
    health: Number(model.health ?? 0),
    description: String(model.description ?? ""),
    dataFlowRate: String(model.dataFlowRate ?? model.data_flow_rate ?? "0 MB/s"),
    requestsToday: Number(model.requestsToday ?? model.requests_today ?? 0),
    latency: Number(model.latency ?? 0),
    category: String(model.category ?? lookupConnectorCategory(vendor) ?? ""),
    authType: authType === "oauth" || authType === "webhook" ? authType : "apiKey",
    authStatus: authStatus || undefined,
    blockingReason: availability?.blockingReason,
    recoveryAction: availability?.recoveryAction,
    availability,
    usedByWorkflows: Number(model.usedByWorkflows ?? model.used_by_workflows ?? 0),
    triggeredByAgents: Number(model.triggeredByAgents ?? model.triggered_by_agents ?? 0),
    config:
      model.config && typeof model.config === "object"
        ? (model.config as Connector["config"])
        : undefined,
  }
}

function normalizeConnectorsResponse(payload: unknown): Connector[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw =
    (Array.isArray(model.connectors) ? model.connectors : null) ??
    (Array.isArray(model.data) ? model.data : null) ??
    (Array.isArray(model.items) ? model.items : null)
  if (!raw) return []
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => normalizeConnector(item))
    .filter((item) => item.id.length > 0)
}

function apiDetailMessage(err: unknown): string | null {
  if (err instanceof ApiRequestError) {
    const payload = err.payload
    if (payload && typeof payload === "object") {
      const detail = (payload as { detail?: unknown }).detail
      if (typeof detail === "string" && detail.trim()) return detail
      if (detail && typeof detail === "object") {
        const message = (detail as { message?: unknown }).message
        if (typeof message === "string" && message.trim()) return message
      }
    }
  }
  if (err instanceof Error && err.message.trim()) return err.message
  return null
}

/** Soften long infra/SQL detail for toast copy (full detail stays in console). */
function toastFriendlyDetail(raw: string | null, fallback: string): string {
  if (!raw?.trim()) return fallback
  const text = raw.replace(/\s+/g, " ").trim()
  const lower = text.toLowerCase()
  if (
    lower.includes("supabase/migrations") ||
    lower.includes("relation") && lower.includes("does not exist") ||
    lower.includes("undefinedcolumn") ||
    lower.includes("pgrst")
  ) {
    return "A backend data schema issue blocked this connection. Try again or contact support if it persists."
  }
  if (text.length > 160) return `${text.slice(0, 157)}…`
  return text
}

function oauthErrorMessage(err: unknown, providerLabel: string): string {
  return toastFriendlyDetail(
    apiDetailMessage(err),
    `${providerLabel} OAuth is not configured on the API host`,
  )
}

function connectorErrorMessage(err: unknown): string {
  return toastFriendlyDetail(
    apiDetailMessage(err),
    "Something went wrong while saving the connector.",
  )
}

const statusConfig = {
  connected: { 
    color: "text-success", 
    bg: "bg-emerald-500", 
    ring: "ring-success/30",
    glow: "shadow-success/20",
    icon: CheckCircle2,
    label: "Connected" 
  },
  disconnected: { 
    color: "text-zinc-500", 
    bg: "bg-zinc-500", 
    ring: "ring-zinc-500/30",
    glow: "shadow-zinc-500/10",
    icon: WifiOff,
    label: "Disconnected" 
  },
  error: { 
    color: "text-destructive", 
    bg: "bg-red-500", 
    ring: "ring-destructive/30",
    glow: "shadow-destructive/20",
    icon: XCircle,
    label: "Error" 
  },
  syncing: { 
    color: "text-blue-500", 
    bg: "bg-blue-500", 
    ring: "ring-blue-500/30",
    glow: "shadow-blue-500/20",
    icon: Loader2,
    label: "Syncing" 
  },
}

// Animated Data Flow Line
function DataFlowLine({ active, direction = "right" }: { active: boolean; direction?: "right" | "left" }) {
  return (
    <div className="relative h-0.5 flex-1 bg-border/30 overflow-hidden">
      {active && (
        <motion.div
          className="absolute inset-y-0 w-8 bg-gradient-to-r from-transparent via-blue-500 to-transparent"
          animate={{ x: direction === "right" ? ["-100%", "400%"] : ["400%", "-100%"] }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
      )}
    </div>
  )
}

// Central Hub Node
function CentralHub({ connectedCount, totalCount }: { connectedCount: number; totalCount: number }) {
  return (
    <div className="relative">
      {/* Outer glow rings */}
      <div className="absolute inset-0 rounded-full bg-blue-500/10 animate-ping" style={{ animationDuration: "3s" }} />
      <div className="absolute -inset-2 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 blur-xl" />
      
      {/* Main hub */}
      <div className="relative flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-card to-secondary border-2 border-blue-500/30 shadow-2xl shadow-blue-500/10">
        <div className="text-center">
          <Cable className="h-8 w-8 text-blue-400 mx-auto mb-1" />
          <div className="text-2xl font-bold text-foreground">{connectedCount}</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">of {totalCount} Active</div>
        </div>
      </div>
    </div>
  )
}

// Connector Node in topology view
function ConnectorNode({ 
  connector, 
  position,
  onConfigure,
  onSync,
  onTestConnection,
  onReconnect,
  onDelete,
}: { 
  connector: Connector
  position: "left" | "right"
  onConfigure: () => void
  onSync: (connectorId: string) => Promise<void>
  onTestConnection: (connectorId: string) => Promise<void>
  onReconnect?: (connector: Connector) => Promise<void>
  onDelete: () => void
}) {
  const [isHovered, setIsHovered] = useState(false)
  const config = statusConfig[connector.status] ?? statusConfig.disconnected
  const StatusIcon = config.icon
  const isSyncing = connector.status === "syncing"

  const handleSync = async () => {
    await onSync(connector.id)
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: position === "left" ? -20 : 20 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "relative group",
        position === "left" ? "flex-row-reverse" : "flex-row"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Connection line */}
      <div className={cn(
        "flex items-center gap-2",
        position === "left" ? "flex-row-reverse" : "flex-row"
      )}>
        {/* Node */}
        <div className={cn(
          "relative rounded-xl border bg-card p-3 md:p-4 transition-all duration-300 w-full md:min-w-[240px]",
          isHovered ? "border-foreground/20 shadow-lg" : "border-border",
          connector.status === "connected" && "shadow-success/5",
          connector.status === "error" && "shadow-destructive/5 border-destructive/30"
        )}>
          {/* Status indicator */}
          <div className={cn(
            "absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full flex items-center justify-center ring-4 ring-card",
            config.bg
          )}>
            {isSyncing ? (
              <Loader2 className="h-2.5 w-2.5 text-white animate-spin" />
            ) : (
              <div className="h-1.5 w-1.5 rounded-full bg-white" />
            )}
          </div>

          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              <ConnectorIcon 
                vendor={connector.type} 
                status={connector.status === "syncing" ? "syncing" : connector.status === "connected" ? "connected" : connector.status === "error" ? "error" : "disconnected"}
                size="sm"
                showStatusIndicator={false}
              />
              <div>
                <h3 className="text-sm font-medium text-foreground">{connector.name}</h3>
                <p className="text-[10px] text-muted-foreground">{connector.type}</p>
              </div>
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-6 w-6 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 focus-visible:opacity-100" aria-label={`${connector.name} options`}>
                  <MoreVertical className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-36">
                <DropdownMenuItem onClick={onConfigure}>
                  <Settings className="h-3.5 w-3.5 mr-2" />
                  Configure
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleSync} disabled={isSyncing}>
                  <RefreshCw className={cn("h-3.5 w-3.5 mr-2", isSyncing && "animate-spin")} />
                  Sync Now
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => void onTestConnection(connector.id)}>
                  <Wifi className="h-3.5 w-3.5 mr-2" />
                  Test Connection
                </DropdownMenuItem>
                {connectorNeedsOAuthReconnect(connector) && onReconnect && (
                    <DropdownMenuItem onClick={() => void onReconnect(connector)}>
                      <ExternalLink className="h-3.5 w-3.5 mr-2" />
                      {connector.authStatus === "auth_expired" ? "Reconnect OAuth" : "Complete OAuth"}
                    </DropdownMenuItem>
                  )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={onDelete} className="text-destructive">
                  <Trash2 className="h-3.5 w-3.5 mr-2" />
                  Remove
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <ConnectorReadinessBadges availability={connector.availability} />

          {connector.availability?.requirementNote ? (
            <p className="mb-2 text-[11px] text-muted-foreground text-pretty">
              {connector.availability.requirementNote}
            </p>
          ) : null}
          {connector.availability?.discoveryLimitation ? (
            <p
              className="mb-2 text-[11px] text-warning text-pretty"
              data-testid="apollo-discovery-limitation"
            >
              {connector.availability.discoveryLimitation}
            </p>
          ) : null}
          {connector.availability?.capabilityNotes?.length ? (
            <ul className="mb-2 space-y-0.5 pl-4 text-[11px] text-muted-foreground list-disc">
              {connector.availability.capabilityNotes.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}

          {/* Live metrics */}
          <div className="grid grid-cols-3 gap-2 p-2 rounded-lg bg-secondary/50 mb-3">
            <div className="text-center">
              <div className="text-xs font-medium text-foreground">{connector.dataFlowRate}</div>
              <div className="text-[9px] text-muted-foreground">Throughput</div>
            </div>
            <div className="text-center border-x border-border/50">
              <div className="text-xs font-medium text-foreground">{connector.latency}ms</div>
              <div className="text-[9px] text-muted-foreground">Latency</div>
            </div>
            <div className="text-center">
              <div className="text-xs font-medium text-foreground">{(connector.requestsToday || 0).toLocaleString()}</div>
              <div className="text-[9px] text-muted-foreground">Requests</div>
            </div>
          </div>

          {/* AI Usage Indicators */}
          {(connector.usedByWorkflows || connector.triggeredByAgents) && connectorIsExecutable(connector) && (
            <div className="flex items-center gap-3 mb-3 text-[10px] text-muted-foreground">
              {connector.usedByWorkflows && connector.usedByWorkflows > 0 && (
                <div className="flex items-center gap-1">
                  <Workflow className="h-3 w-3 text-blue-400" />
                  <span>{connector.usedByWorkflows} workflows</span>
                </div>
              )}
              {connector.triggeredByAgents && connector.triggeredByAgents > 0 && (
                <div className="flex items-center gap-1">
                  <Bot className="h-3 w-3 text-violet-400" />
                  <span>{connector.triggeredByAgents} agents</span>
                </div>
              )}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <StatusIcon className={cn("h-3 w-3", config.color, isSyncing && "animate-spin")} />
              <span className={cn("text-[10px] font-medium", config.color)}>
                {isSyncing ? "Syncing..." : connectorStatusLabel(connector)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {connectorNeedsOAuthReconnect(connector) && onReconnect && (
                  <button
                    type="button"
                    className="text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                    onClick={() => void onReconnect(connector)}
                  >
                    {connector.authStatus === "auth_expired" ? "Reconnect OAuth" : "Complete OAuth"}
                  </button>
                )}
              <Link 
                href={`/connectors/${connector.id}`}
                className="text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                Details
              </Link>
              <span className={cn(
                "text-[10px] px-1.5 py-0.5 rounded",
                connector.environment === "production" 
                  ? "bg-success/10 text-success" 
                  : "bg-warning/10 text-warning"
              )}>
                {connector.environment}
              </span>
            </div>
          </div>
        </div>

        {/* Data flow line - hidden on mobile */}
        <div className="hidden md:flex w-16 items-center">
          <DataFlowLine active={connectorIsExecutable(connector)} direction={position === "left" ? "right" : "left"} />
        </div>
      </div>
    </motion.div>
  )
}

// Configure Modal
function ConfigureModal({
  connector,
  open,
  onClose,
  onSave,
  onReconnectOAuth,
}: {
  connector: Connector
  open: boolean
  onClose: () => void
  onSave: (connectorId: string, config: Connector["config"]) => Promise<void>
  onReconnectOAuth?: (connector: Connector) => Promise<void>
}) {
  const [config, setConfig] = useState(connector.config || {})
  const [showApiKey, setShowApiKey] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const isOAuth = connector.authType === "oauth"

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await onSave(connector.id, config)
      onClose()
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <ConnectorIcon vendor={connector.type} size="md" />
            <div>
              <DialogTitle>{connector.name}</DialogTitle>
              <DialogDescription>{connector.type} Configuration</DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {isOAuth ? (
            <div className="rounded-lg border border-border bg-secondary/40 p-4 space-y-3">
              <p className="text-sm text-muted-foreground">
                {connector.authStatus === "auth_expired"
                  ? `${connector.type} authorization expired or was revoked in the provider. Re-authorize to restore the connection.`
                  : `${connector.type} uses OAuth. API keys are not used for this connector — authorize with the provider to connect.`}
              </p>
              {onReconnectOAuth && (
                <Button
                  type="button"
                  className="w-full gap-2"
                  onClick={() => void onReconnectOAuth(connector)}
                >
                  <ExternalLink className="h-4 w-4" />
                  {connector.authStatus === "auth_expired" ? `Reconnect ${connector.type}` : "Complete OAuth"}
                </Button>
              )}
            </div>
          ) : (
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">API Key</label>
            <div className="relative">
              <Input
                type={showApiKey ? "text" : "password"}
                value={config.apiKey || ""}
                onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                className="pr-10 bg-secondary"
                placeholder="Enter API key or secret"
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
          )}
          {!isOAuth && (
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Sync Interval</label>
            <select
              value={config.syncInterval || "5m"}
              onChange={(e) => setConfig({ ...config, syncInterval: e.target.value })}
              className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm"
            >
              <option value="1m">Every 1 minute</option>
              <option value="5m">Every 5 minutes</option>
              <option value="15m">Every 15 minutes</option>
              <option value="30m">Every 30 minutes</option>
              <option value="1h">Every 1 hour</option>
            </select>
          </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{isOAuth ? "Close" : "Cancel"}</Button>
          {!isOAuth && (
          <Button onClick={handleSave} disabled={isSaving || !config.apiKey?.trim()}>
            {isSaving ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving...</> : "Save Changes"}
          </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Delete Modal
function DeleteModal({
  connector,
  open,
  onClose,
  onConfirm,
}: {
  connector: Connector
  open: boolean
  onClose: () => void
  onConfirm: (connectorId: string, confirmName: string) => Promise<void>
}) {
  const [confirmText, setConfirmText] = useState("")
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async () => {
    setIsDeleting(true)
    try {
      await onConfirm(connector.id, confirmText)
      onClose()
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <div>
              <DialogTitle>Remove Connector</DialogTitle>
              <DialogDescription>This cannot be undone</DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <div className="py-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            Type <span className="font-mono text-foreground">{connector.name}</span> to confirm removal.
          </p>
          <Input
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={connector.name}
            className="bg-secondary"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" onClick={handleDelete} disabled={confirmText !== connector.name || isDeleting}>
            {isDeleting ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Removing...</> : "Remove"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const connectorCategories = CONNECTOR_CATEGORIES

// Flatten for search
const availableConnectors = Object.entries(connectorCategories).flatMap(([category, data]) =>
  data.connectors.map((c) => ({ ...c, category }))
)

type CatalogConnector = (typeof availableConnectors)[number] & {
  vendorKey?: string
  shipped?: boolean
  oauthReady?: boolean
  credentialModel?: string
  requiresSubdomain?: boolean
  requiresInstanceUrl?: boolean
  requiresPartnerApproval?: boolean
  partner?: boolean
  certified?: boolean
}

// Add Connector Modal
function AddConnectorModal({
  open,
  onClose,
  onCreated,
  existingConnectors,
  publishedConnectors = [],
  initialConnectorType = null,
}: {
  open: boolean
  onClose: () => void
  onCreated: () => Promise<void>
  existingConnectors: Connector[]
  publishedConnectors?: Array<{
    name: string
    vendor: string
    description: string
    authType: "oauth" | "apiKey"
    certificationBadge?: string | null
  }>
  initialConnectorType?: string | null
}) {
  const [step, setStep] = useState<"select" | "configure" | "oauth" | "webhook">("select")
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [selectedAuthType, setSelectedAuthType] = useState<"oauth" | "apiKey" | "webhook" | null>(null)
  const [name, setName] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [apiSecret, setApiSecret] = useState("")
  const [environment, setEnvironment] = useState<AppEnvironment>(() => getSelectedEnvironmentFromStorage())
  const [isCreating, setIsCreating] = useState(false)
  const [oauthStatus, setOauthStatus] = useState<"idle" | "redirecting" | "success" | "error">("idle")
  const [searchQuery, setSearchQuery] = useState("")
  const [modalCategoryFilter, setModalCategoryFilter] = useState<string>("all")
  const [copied, setCopied] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [zendeskSubdomain, setZendeskSubdomain] = useState("")
  const [zendeskEmail, setZendeskEmail] = useState("")
  const [githubOwner, setGithubOwner] = useState("")
  const [githubRepo, setGithubRepo] = useState("")
  const [oauthSubdomain, setOauthSubdomain] = useState("")
  const [oauthInstanceUrl, setOauthInstanceUrl] = useState("")
  const [odooUrl, setOdooUrl] = useState("")
  const [odooUsername, setOdooUsername] = useState("")
  const [odooDatabase, setOdooDatabase] = useState("")
  const [clayWebhookUrl, setClayWebhookUrl] = useState("")
  const [clayTableName, setClayTableName] = useState("")

  const catalogConnectors = useMemo<CatalogConnector[]>(() => {
    const partnerEntries: CatalogConnector[] = publishedConnectors.map((entry) => ({
      type: entry.name,
      description: entry.description || `Partner connector · ${entry.vendor}`,
      authType: entry.authType,
      category: "Partner Marketplace",
      vendorKey: entry.vendor,
      partner: true,
      certified: entry.certificationBadge === "gravitre_certified",
    }))
    return [...availableConnectors, ...partnerEntries]
  }, [publishedConnectors])

  const resolveVendor = (connector: CatalogConnector | undefined, type: string) =>
    connector?.vendorKey || connectorVendorKey(type)

  // Webhook URL for webhook-based connectors
  const webhookUrl = `${publicApiUrl()}/webhooks/${selectedType?.toLowerCase().replace(/\s+/g, "-")}/incoming`

  const filteredModalConnectors = catalogConnectors.filter((c) => {
    const matchesSearch = c.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.category.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = modalCategoryFilter === "all" || c.category === modalCategoryFilter
    return matchesSearch && matchesCategory
  })

  const groupedConnectors = filteredModalConnectors.reduce((acc, c) => {
    if (!acc[c.category]) acc[c.category] = []
    acc[c.category].push(c)
    return acc
  }, {} as Record<string, CatalogConnector[]>)

  const getSelectedConnector = () => catalogConnectors.find((c) => c.type === selectedType)

  const selectedConnectorMeta = () => getSelectedConnector()

  const selectedSupportsDualPat = () => {
    const connector = selectedConnectorMeta()
    return connector ? supportsDualPatAuth(connector) && connector.oauthReady === true : false
  }

  const switchToPatAuth = () => {
    setSelectedAuthType("apiKey")
    setStep("configure")
    setOauthStatus("idle")
  }

  const switchToOAuthAuth = () => {
    const connector = selectedConnectorMeta()
    setSelectedAuthType("oauth")
    setStep("oauth")
    setOauthStatus("idle")
    if (connector?.requiresSubdomain && zendeskSubdomain.trim()) {
      setOauthSubdomain(zendeskSubdomain.trim())
    }
  }

  const oauthExtraFields = () => {
    const connector = selectedConnectorMeta()
    const extra: { subdomain?: string; instanceUrl?: string; owner?: string; repo?: string } = {}
    if (connector?.requiresSubdomain && oauthSubdomain.trim()) {
      extra.subdomain = oauthSubdomain.trim()
    }
    if (connector?.requiresInstanceUrl && oauthInstanceUrl.trim()) {
      extra.instanceUrl = oauthInstanceUrl.trim()
    }
    if (selectedType === "GitHub") {
      if (githubOwner.trim()) extra.owner = githubOwner.trim()
      if (githubRepo.trim()) extra.repo = githubRepo.trim()
    }
    return extra
  }

  const canStartOAuth = (): boolean => {
    if (!name.trim()) return false
    const connector = selectedConnectorMeta()
    if (connector?.requiresSubdomain && !oauthSubdomain.trim()) return false
    if (connector?.requiresInstanceUrl && !oauthInstanceUrl.trim()) return false
    return true
  }

  const handleOAuthConnect = async () => {
    if (!selectedType || !canStartOAuth()) return
    const selected = getSelectedConnector()
    const provider = resolveVendor(selected, selectedType)
    const existing = existingConnectors.find(
      (c) =>
        connectorVendorKey(c.type) === provider ||
        c.name.trim().toLowerCase() === name.trim().toLowerCase()
    )

    // Plaid uses Link (platform PLAID_* keys), not /oauth/{provider}/start.
    if (isPlaidLinkConnector(selected) || provider === "plaid") {
      setOauthStatus("redirecting")
      try {
        const { linkToken } = await connectorsApi.plaidCreateLinkToken({
          name: name.trim() || existing?.name || "plaid-sandbox",
          connectorId: existing?.id,
          redirectUri: "https://gravitre.app/connectors",
        })
        if (!linkToken) throw new Error("Plaid did not return a link token")
        await openPlaidLink({
          linkToken,
          onSuccess: async (publicToken, metadata) => {
            try {
              await connectorsApi.plaidExchangePublicToken({
                publicToken,
                name: name.trim() || existing?.name || "plaid-sandbox",
                connectorId: existing?.id,
                metadata,
              })
              setOauthStatus("success")
              toast.success("Plaid connected (Sandbox)")
              // Refresh connector list after Link closes.
              window.setTimeout(() => {
                window.location.assign("/connectors?oauth=success&provider=plaid")
              }, 600)
            } catch (err) {
              console.error("[connectors] Plaid exchange failed:", err)
              setOauthStatus("error")
              toast.error("Failed to save Plaid connection", {
                description: oauthErrorMessage(err, "Plaid"),
              })
            }
          },
          onExit: (err) => {
            if (err) {
              setOauthStatus("error")
              toast.error("Plaid Link closed with an error")
            } else {
              setOauthStatus("idle")
            }
          },
        })
      } catch (err) {
        console.error("[connectors] Plaid Link start failed:", err)
        setOauthStatus("error")
        toast.error("Failed to start Plaid Link", {
          description: oauthErrorMessage(err, "Plaid"),
        })
      }
      return
    }

    const extra = oauthExtraFields()
    setOauthStatus("redirecting")
    try {
      const { authorizationUrl } = existing
        ? await connectorsApi.reconnectOAuth(provider, existing.id, existing.name, extra)
        : await connectorsApi.startOAuth(provider, {
            name,
            redirectPath: "/connectors",
            ...extra,
          })
      window.location.assign(authorizationUrl)
    } catch (err) {
      console.error("[connectors] OAuth start failed:", err)
      setOauthStatus("error")
      toast.error(`Failed to connect ${selectedType}`, {
        description: oauthErrorMessage(err, selectedType),
      })
    }
  }

  const canSubmitApiKey = (): boolean => {
    if (!name) return false
    if (selectedType === "Zendesk") {
      return Boolean(zendeskSubdomain && zendeskEmail && apiKey)
    }
    if (selectedType === "GitHub") {
      return Boolean(githubOwner && githubRepo && apiKey)
    }
    if (selectedType === "Odoo") {
      return Boolean(odooUrl && odooUsername && apiKey)
    }
    if (selectedType === "Clay") {
      return Boolean(apiKey && clayWebhookUrl.trim())
    }
    return Boolean(apiKey)
  }

  const handleConnect = async () => {
    if (!selectedType || !name) return
    if (selectedAuthType === "apiKey" && !canSubmitApiKey()) return
    setIsCreating(true)
    await completeConnection()
  }

  const pickEnvironment = (env: AppEnvironment) => {
    setEnvironment(env)
    setSelectedEnvironmentInStorage(env)
  }

  const completeConnection = async () => {
    if (!selectedType || !name) return
    setSelectedEnvironmentInStorage(environment)
    setIsCreating(true)
    try {
      const vendor = resolveVendor(getSelectedConnector(), selectedType)
      const payload: import("@/types/api").CreateConnectorRequest = {
        name,
        vendor,
        description: getSelectedConnector()?.description,
        sync_frequency: "5m",
      }
      if (selectedType === "Zendesk") {
        payload.config = { subdomain: zendeskSubdomain.trim() }
        payload.secrets = {
          email: zendeskEmail.trim(),
          api_token: apiKey.trim(),
        }
      } else if (selectedType === "GitHub") {
        payload.config = { owner: githubOwner.trim(), repo: githubRepo.trim() }
        payload.secrets = { token: apiKey.trim() }
      } else if (selectedType === "Odoo") {
        payload.config = {
          odoo_url: odooUrl.trim(),
          ...(odooDatabase.trim() ? { database: odooDatabase.trim() } : {}),
        }
        payload.secrets = { username: odooUsername.trim() }
        payload.api_key = apiKey.trim()
        ;(payload as { apiKey?: string }).apiKey = apiKey.trim()
      } else if (selectedType === "Clay") {
        payload.config = {
          webhook_url: clayWebhookUrl.trim(),
          ...(clayTableName.trim() ? { table_name: clayTableName.trim() } : {}),
        }
        payload.webhook_url = clayWebhookUrl.trim()
        payload.api_key = apiKey.trim()
        ;(payload as { apiKey?: string }).apiKey = apiKey.trim()
      } else if (apiKey) {
        payload.api_key = apiKey
        ;(payload as { apiKey?: string }).apiKey = apiKey
      }
      await connectorsApi.create(payload)
      toast.success("Connector added", { description: `${selectedType} has been connected successfully` })
      await onCreated()
      handleClose()
    } catch (err) {
      console.error("[connectors] Failed to create connector:", err)
      toast.error("Failed to create connector", {
        description: connectorErrorMessage(err),
      })
    } finally {
      setIsCreating(false)
    }
  }

  const handleCopyWebhook = () => {
    navigator.clipboard.writeText(webhookUrl)
    setCopied(true)
    toast.success("Webhook URL copied to clipboard")
    setTimeout(() => setCopied(false), 2000)
  }

  const handleClose = () => {
    setStep("select")
    setSelectedType(null)
    setSelectedAuthType(null)
    setName("")
    setApiKey("")
    setApiSecret("")
    setEnvironment("production")
    setSelectedEnvironmentInStorage("production")
    setSearchQuery("")
    setModalCategoryFilter("all")
    setOauthStatus("idle")
    setCopied(false)
    setShowApiKey(false)
    setZendeskSubdomain("")
    setZendeskEmail("")
    setGithubOwner("")
    setGithubRepo("")
    setOauthSubdomain("")
    setOauthInstanceUrl("")
    setOdooUrl("")
    setOdooUsername("")
    setOdooDatabase("")
    setClayWebhookUrl("")
    setClayTableName("")
    onClose()
  }

  const handleSelectConnector = (connector: CatalogConnector) => {
    if (connector.partner) {
      toast.message(`${connector.type} is a partner integration`, {
        description: "Install from the marketplace or contact sales for certified connectors.",
      })
      return
    }
    if (isPartnerGatedConnector(connector)) {
      toast.message(`${connector.type} requires partner access`, {
        description: "Contact sales@gravitre.app to enable this integration for your organization.",
      })
      return
    }
    if (!isShippedConnector(connector)) {
      toast.message(`${connector.type} is coming soon`, {
        description: "This integration is listed for planning; connect shipped apps marked Available.",
      })
      return
    }
    setSelectedType(connector.type)
    setSelectedAuthType(connector.authType as "oauth" | "apiKey" | "webhook")
    const vendorSlug = (connector.vendorKey || connector.type).toLowerCase().replace(/\s+/g, "-")
    setName(`${vendorSlug}-${environment}`)

    // Route to appropriate auth flow
    if (connector.authType === "oauth") {
      setStep("oauth")
    } else if (connector.authType === "webhook") {
      setStep("webhook")
    } else {
      setStep("configure")
    }
  }

  useEffect(() => {
    if (!open || !initialConnectorType) return
    const preset = initialConnectorType.trim()
    if (!preset) return
    const connector = catalogConnectors.find(
      (entry) =>
        entry.type === preset ||
        entry.vendorKey === preset ||
        connectorVendorKey(entry.type) === connectorVendorKey(preset),
    )
    if (connector) handleSelectConnector(connector)
  }, [open, initialConnectorType, catalogConnectors])

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-2xl bg-card border-border max-h-[min(85vh,900px)] min-h-0 overflow-hidden flex flex-col gap-0 p-0">
        <DialogHeader className="shrink-0 px-6 pt-6 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 ring-1 ring-blue-500/20">
              <Plus className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <DialogTitle>
                {step === "select" ? "Add Connector" : `Configure ${selectedType}`}
              </DialogTitle>
              <DialogDescription>
                {step === "select" 
                  ? "Choose a connector type to integrate with your workflows" 
                  : "Enter the credentials and settings for this connector"
                }
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6">
        <AnimatePresence mode="wait">
          {step === "select" ? (
            <motion.div
              key="select"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="flex flex-col pb-2"
            >
              {/* Search */}
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search connectors..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 bg-secondary"
                />
              </div>

              {/* Category Filter Tabs */}
              <div className="flex flex-wrap gap-1.5 mb-4 pb-3 border-b border-border">
                <button
                  onClick={() => setModalCategoryFilter("all")}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs font-medium transition-all",
                    modalCategoryFilter === "all"
                      ? "bg-blue-500 text-white"
                      : "bg-secondary text-muted-foreground hover:text-foreground hover:bg-secondary/80"
                  )}
                >
                  All ({availableConnectors.length})
                </button>
                {Object.entries(connectorCategories).map(([cat, data]) => {
                  const colorMap: Record<string, { active: string, inactive: string }> = {
                    emerald: { active: "bg-emerald-500 text-white", inactive: "hover:bg-emerald-500/10 hover:text-emerald-400" },
                    blue: { active: "bg-blue-500 text-white", inactive: "hover:bg-blue-500/10 hover:text-blue-400" },
                    violet: { active: "bg-violet-500 text-white", inactive: "hover:bg-violet-500/10 hover:text-violet-400" },
                    amber: { active: "bg-amber-500 text-white", inactive: "hover:bg-amber-500/10 hover:text-amber-400" },
                    pink: { active: "bg-pink-500 text-white", inactive: "hover:bg-pink-500/10 hover:text-pink-400" },
                    cyan: { active: "bg-cyan-500 text-white", inactive: "hover:bg-cyan-500/10 hover:text-cyan-400" },
                    orange: { active: "bg-orange-500 text-white", inactive: "hover:bg-orange-500/10 hover:text-orange-400" },
                    indigo: { active: "bg-indigo-500 text-white", inactive: "hover:bg-indigo-500/10 hover:text-indigo-400" },
                  }
                  const colors = colorMap[data.color] || colorMap.blue
                  return (
                    <button
                      key={cat}
                      onClick={() => setModalCategoryFilter(cat)}
                      className={cn(
                        "px-3 py-1.5 rounded-full text-xs font-medium transition-all",
                        modalCategoryFilter === cat
                          ? colors.active
                          : `bg-secondary text-muted-foreground ${colors.inactive}`
                      )}
                    >
                      {cat.split(" / ")[0]} ({data.connectors.length})
                    </button>
                  )
                })}
              </div>

              {/* Connector Grid */}
              <div className="space-y-4">
                {Object.keys(groupedConnectors).length === 0 && (
                  <div className="text-center py-8">
                    <p className="text-sm text-muted-foreground">No connectors found</p>
                    <button 
                      onClick={() => { setSearchQuery(""); setModalCategoryFilter("all"); }}
                      className="text-xs text-blue-400 hover:text-blue-300 mt-1"
                    >
                      Clear filters
                    </button>
                  </div>
                )}
                {Object.entries(groupedConnectors).map(([category, connectors]) => (
                  <div key={category}>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                      {category}
                    </h4>
                    <div className="grid grid-cols-2 gap-2">
                      {connectors.map((connector) => (
                        <button
                          key={connector.type}
                          onClick={() => handleSelectConnector(connector)}
                          className={cn(
                            "group flex items-center gap-3 rounded-lg border border-border bg-secondary/30 p-3 text-left transition-all hover:border-blue-500/30 hover:bg-blue-500/5",
                            selectedType === connector.type && "border-blue-500 bg-blue-500/10"
                          )}
                        >
<ConnectorIcon vendor={connector.type} size="sm" />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-foreground">{connector.type}</span>
                              {connector.certified && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded uppercase font-medium bg-success/10 text-success">
                                  Certified
                                </span>
                              )}
                              {!connector.partner && isPartnerGatedConnector(connector) && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded uppercase font-medium bg-warning/10 text-warning">
                                  Partner
                                </span>
                              )}
                              {!connector.partner && isShippedConnector(connector) && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded uppercase font-medium bg-success/10 text-success">
                                  Available
                                </span>
                              )}
                              <span className={cn(
                                "text-[9px] px-1.5 py-0.5 rounded uppercase font-medium",
                                isPartnerGatedConnector(connector)
                                  ? "bg-warning/10 text-warning"
                                  : !connector.partner && !isShippedConnector(connector)
                                  ? "bg-zinc-500/10 text-zinc-400"
                                  : connector.authType === "oauth"
                                    ? "bg-blue-500/10 text-blue-400"
                                    : connector.authType === "webhook"
                                      ? "bg-violet-500/10 text-violet-400"
                                      : "bg-warning/10 text-warning"
                              )}>
                                {isPartnerGatedConnector(connector)
                                  ? "Request access"
                                  : !connector.partner && !isShippedConnector(connector)
                                  ? "Coming soon"
                                  : connector.authType === "oauth"
                                    ? "OAuth"
                                    : connector.authType === "webhook"
                                      ? "Webhook"
                                      : "API Key"}
                              </span>
                            </div>
                            <div className="text-xs text-muted-foreground truncate">{connector.description}</div>
                          </div>
                          <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          ) : step === "oauth" ? (
            // OAuth Connection Flow
            <motion.div
              key="oauth"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4 py-2"
            >
              {/* Selected Connector Preview */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 p-3">
                <ConnectorIcon vendor={selectedType || ""} size="sm" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{selectedType}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 uppercase font-medium">OAuth</span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {getSelectedConnector()?.description}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-xs"
                  onClick={() => setStep("select")}
                  disabled={oauthStatus !== "idle" || isCreating}
                >
                  Change
                </Button>
              </div>

              {/* OAuth Status */}
              <div className="rounded-xl border border-border bg-secondary/30 p-6 text-center">
                {oauthStatus === "idle" && (
                  <div className="space-y-4">
                    <div className="mx-auto h-16 w-16 rounded-full bg-blue-500/10 flex items-center justify-center">
                      <Globe className="h-8 w-8 text-blue-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">Connect with {selectedType}</h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        You&apos;ll be redirected to {selectedType} to authorize Gravitre
                      </p>
                      {selectedConnectorMeta()?.vendorKey &&
                        PKCE_OAUTH_VENDOR_KEYS.has(selectedConnectorMeta()!.vendorKey!) && (
                          <p className="text-[11px] text-muted-foreground mt-2">
                            Uses secure PKCE authorization (required by {selectedType}).
                          </p>
                        )}
                    </div>
                    <div className="space-y-3 text-left max-w-sm mx-auto">
                      <div>
                        <label className="text-xs text-muted-foreground">Connector name</label>
                        <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 bg-secondary" />
                      </div>
                      {selectedConnectorMeta()?.requiresSubdomain && (
                        <div>
                          <label className="text-xs text-muted-foreground">Subdomain / account</label>
                          <Input
                            value={oauthSubdomain}
                            onChange={(e) => setOauthSubdomain(e.target.value)}
                            placeholder="e.g. acme"
                            className="mt-1 bg-secondary"
                          />
                        </div>
                      )}
                      {selectedConnectorMeta()?.requiresInstanceUrl && (
                        <div>
                          <label className="text-xs text-muted-foreground">Instance URL</label>
                          <Input
                            value={oauthInstanceUrl}
                            onChange={(e) => setOauthInstanceUrl(e.target.value)}
                            placeholder="https://mycompany.odoo.com"
                            className="mt-1 bg-secondary"
                          />
                        </div>
                      )}
                      {selectedType === "Apollo" && (
                        <div className="rounded-lg border border-border bg-secondary/40 p-3 space-y-2">
                          <p className="text-xs text-muted-foreground">
                            Sign in with Apollo to authorize Gravitre. Your Apollo admin must approve OAuth
                            integrations for your workspace. Scopes are configured in your Apollo OAuth app
                            registration.
                          </p>
                          <a
                            href="https://docs.apollo.io/docs/use-oauth-20-authorization-flow-to-access-apollo-user-information-partners"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                          >
                            Apollo OAuth partner guide
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </div>
                      )}
                      {selectedType === "GitHub" && (
                        <>
                          <div>
                            <label className="text-xs text-muted-foreground">Owner (org or user)</label>
                            <Input
                              value={githubOwner}
                              onChange={(e) => setGithubOwner(e.target.value)}
                              placeholder="my-org"
                              className="mt-1 bg-secondary"
                            />
                          </div>
                          <div>
                            <label className="text-xs text-muted-foreground">Repository</label>
                            <Input
                              value={githubRepo}
                              onChange={(e) => setGithubRepo(e.target.value)}
                              placeholder="my-repo"
                              className="mt-1 bg-secondary"
                            />
                            <p className="text-[11px] text-muted-foreground mt-1">
                              Optional now — required for repo-scoped agent actions
                            </p>
                          </div>
                        </>
                      )}
                    </div>
                    <Button onClick={handleOAuthConnect} className="gap-2" disabled={!canStartOAuth()}>
                      <ExternalLink className="h-4 w-4" />
                      {isPlaidLinkConnector(getSelectedConnector())
                        ? "Connect with Plaid Link"
                        : `Connect with ${selectedType}`}
                    </Button>
                    {selectedSupportsDualPat() && (
                      <button
                        type="button"
                        onClick={switchToPatAuth}
                        className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
                      >
                        {selectedType === "GitHub"
                          ? "Use personal access token instead"
                          : "Use API token instead"}
                      </button>
                    )}
                  </div>
                )}
                {oauthStatus === "redirecting" && (
                  <div className="flex flex-col items-center gap-4 rounded-2xl border border-border/70 bg-secondary/20 px-6 py-8 text-center shadow-[var(--elevation-1)]">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[color-mix(in_oklch,var(--info)_12%,transparent)] text-[var(--info)] ring-1 ring-[color-mix(in_oklch,var(--info)_28%,transparent)]">
                      <Loader2 className="h-5 w-5 animate-spin" />
                    </div>
                    <div className="space-y-1">
                      <h3 className="text-base font-semibold tracking-tight text-foreground">
                        Connecting to {selectedType}
                      </h3>
                      <p className="text-sm text-muted-foreground">Waiting for authorization…</p>
                    </div>
                  </div>
                )}
                {oauthStatus === "success" && (
                  <div className="flex flex-col items-center gap-4 rounded-2xl border border-primary/20 bg-primary/5 px-6 py-8 text-center shadow-[var(--elevation-1)]">
                    <motion.div
                      initial={{ scale: 0.85, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/25"
                    >
                      <CheckCircle2 className="h-5 w-5" />
                    </motion.div>
                    <div className="space-y-1">
                      <h3 className="text-base font-semibold tracking-tight text-foreground">
                        Connected successfully
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        {selectedType} has been authorized for this organization.
                      </p>
                    </div>
                  </div>
                )}
                {oauthStatus === "error" && (
                  <div className="flex flex-col items-center gap-4 rounded-2xl border border-destructive/20 bg-card px-6 py-8 text-center shadow-[var(--elevation-2)]">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive ring-1 ring-destructive/20">
                      <XCircle className="h-5 w-5" />
                    </div>
                    <div className="space-y-1">
                      <h3 className="text-base font-semibold tracking-tight text-foreground">
                        Connection failed
                      </h3>
                      <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
                        Unable to connect to {selectedType}. Check credentials or try again.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      className="min-w-[8.5rem]"
                      onClick={() => setOauthStatus("idle")}
                    >
                      Try again
                    </Button>
                  </div>
                )}
              </div>

              {/* Environment Selection */}
              {oauthStatus === "idle" && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Environment</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => pickEnvironment("staging")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "staging"
                          ? "border-warning/50 bg-warning/10 text-warning"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "staging" ? "fill-warning text-warning" : "fill-muted-foreground text-muted-foreground")} />
                      Staging
                    </button>
                    <button
                      onClick={() => pickEnvironment("production")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "production"
                          ? "border-success/50 bg-success/10 text-success"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "production" ? "fill-success text-success" : "fill-muted-foreground text-muted-foreground")} />
                      Production
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          ) : step === "webhook" ? (
            // Webhook Connection Flow
            <motion.div
              key="webhook"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4 py-2"
            >
              {/* Selected Connector Preview */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 p-3">
                <ConnectorIcon vendor={selectedType || ""} size="sm" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{selectedType}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 uppercase font-medium">Webhook</span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {getSelectedConnector()?.description}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-xs"
                  onClick={() => setStep("select")}
                >
                  Change
                </Button>
              </div>

              {/* Webhook URL */}
              <div className="rounded-xl border border-border bg-secondary/30 p-4 space-y-4">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Link2 className="h-4 w-4 text-violet-400" />
                  Webhook Endpoint
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-card px-3 py-2 rounded-lg font-mono text-foreground border border-border truncate">
                      {webhookUrl}
                    </code>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={handleCopyWebhook}
                      className="gap-1.5 shrink-0"
                    >
                      {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                      {copied ? "Copied" : "Copy"}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Add this URL to your {selectedType} webhook settings
                  </p>
                </div>
              </div>

              {/* Instructions */}
              <div className="rounded-lg border border-border bg-card p-4 space-y-3">
                <h4 className="text-sm font-medium text-foreground">Setup Instructions</h4>
                <ol className="text-xs text-muted-foreground space-y-2 list-decimal list-inside">
                  <li>Go to your {selectedType} settings or admin panel</li>
                  <li>Navigate to Webhooks or Integrations section</li>
                  <li>Add a new webhook with the URL above</li>
                  <li>Select the events you want to receive</li>
                  <li>Click &quot;Verify Connection&quot; below to confirm</li>
                </ol>
              </div>

              {/* Connector Name & Environment */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Connector Name</label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={`my-${selectedType?.toLowerCase().replace(/\s+/g, "-")}-webhook`}
                    className="bg-secondary"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Environment</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => pickEnvironment("staging")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "staging"
                          ? "border-warning/50 bg-warning/10 text-warning"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "staging" ? "fill-warning text-warning" : "fill-muted-foreground text-muted-foreground")} />
                      Staging
                    </button>
                    <button
                      onClick={() => pickEnvironment("production")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "production"
                          ? "border-success/50 bg-success/10 text-success"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "production" ? "fill-success text-success" : "fill-muted-foreground text-muted-foreground")} />
                      Production
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            // API Key Connection Flow
            <motion.div
              key="configure"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-4 py-2"
            >
              {/* Selected Connector Preview */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/30 p-3">
                <ConnectorIcon vendor={selectedType || ""} size="sm" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{selectedType}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-warning/10 text-warning uppercase font-medium">API Key</span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {getSelectedConnector()?.description}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-xs"
                  onClick={() => setStep("select")}
                >
                  Change
                </Button>
              </div>

              {/* Configuration Form */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Connector Name</label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={`my-${selectedType?.toLowerCase().replace(/\s+/g, "-")}-connector`}
                    className="bg-secondary"
                  />
                  <p className="text-xs text-muted-foreground">
                    A unique identifier for this connector
                  </p>
                </div>

                {selectedType === "Zendesk" && (
                  <>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Zendesk subdomain</label>
                      <Input
                        value={zendeskSubdomain}
                        onChange={(e) => setZendeskSubdomain(e.target.value)}
                        placeholder="your-company"
                        className="bg-secondary"
                      />
                      <p className="text-xs text-muted-foreground">From your-company.zendesk.com</p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Agent email</label>
                      <Input
                        value={zendeskEmail}
                        onChange={(e) => setZendeskEmail(e.target.value)}
                        placeholder="agent@company.com"
                        className="bg-secondary"
                      />
                    </div>
                  </>
                )}

                {selectedType === "GitHub" && (
                  <>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Owner (org or user)</label>
                      <Input
                        value={githubOwner}
                        onChange={(e) => setGithubOwner(e.target.value)}
                        placeholder="my-org"
                        className="bg-secondary"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Repository</label>
                      <Input
                        value={githubRepo}
                        onChange={(e) => setGithubRepo(e.target.value)}
                        placeholder="my-repo"
                        className="bg-secondary"
                      />
                    </div>
                  </>
                )}

                {selectedType === "Odoo" && (
                  <>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Odoo URL</label>
                      <Input
                        value={odooUrl}
                        onChange={(e) => setOdooUrl(e.target.value)}
                        placeholder="https://company.odoo.com"
                        className="bg-secondary"
                      />
                      <p className="text-xs text-muted-foreground">Your Odoo SaaS or self-hosted base URL</p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Username</label>
                      <Input
                        value={odooUsername}
                        onChange={(e) => setOdooUsername(e.target.value)}
                        placeholder="admin@company.com"
                        className="bg-secondary"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Database (optional)</label>
                      <Input
                        value={odooDatabase}
                        onChange={(e) => setOdooDatabase(e.target.value)}
                        placeholder="company"
                        className="bg-secondary"
                      />
                      <p className="text-xs text-muted-foreground">Auto-detected from *.odoo.com URLs when omitted</p>
                    </div>
                  </>
                )}

                {selectedType === "Clay" && (
                  <>
                    <div className="rounded-lg border border-border bg-secondary/40 p-3 space-y-2">
                      <p className="text-xs text-muted-foreground">
                        Clay uses API keys for Enterprise lookups and table webhooks for pushing leads into enrichment
                        workflows. Copy your API key from Clay Settings → API and your table webhook from the table’s
                        webhook source column.
                      </p>
                      <a
                        href="https://university.clay.com/docs/using-clay-as-an-api"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                      >
                        Clay API guide
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Table webhook URL</label>
                      <Input
                        value={clayWebhookUrl}
                        onChange={(e) => setClayWebhookUrl(e.target.value)}
                        placeholder="https://app.clay.com/api/v1/webhooks/..."
                        className="bg-secondary"
                      />
                      <p className="text-xs text-muted-foreground">
                        Used to push leads and enrichment requests into your Clay table
                      </p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Table name (optional)</label>
                      <Input
                        value={clayTableName}
                        onChange={(e) => setClayTableName(e.target.value)}
                        placeholder="Lead enrichment"
                        className="bg-secondary"
                      />
                    </div>
                  </>
                )}

                <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground flex items-center gap-2">
                      <Key className="h-4 w-4 text-warning" />
                      {selectedType === "Zendesk"
                        ? "API token"
                        : selectedType === "GitHub"
                          ? "Personal access token"
                          : selectedType === "Odoo"
                            ? "API key"
                            : selectedType === "Clay"
                              ? "Clay API key"
                              : "API Key"}
                    </label>
                    <div className="relative">
                      <Input
                        type={showApiKey ? "text" : "password"}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder={
                          selectedType === "Clay"
                            ? "Paste your Clay API key from Settings → API"
                            : "Enter your API key or token"
                        }
                        className="bg-secondary pr-10"
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

                {/* Optional API Secret for some services */}
                {(selectedType === "Stripe" || selectedType === "AWS S3") && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      {selectedType === "AWS S3" ? "Secret Access Key" : "API Secret"} (Optional)
                    </label>
                    <Input
                      type="password"
                      value={apiSecret}
                      onChange={(e) => setApiSecret(e.target.value)}
                      placeholder={selectedType === "AWS S3" ? "Enter your secret access key" : "Enter API secret"}
                      className="bg-secondary"
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Environment</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => pickEnvironment("staging")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "staging"
                          ? "border-warning/50 bg-warning/10 text-warning"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "staging" ? "fill-warning text-warning" : "fill-muted-foreground text-muted-foreground")} />
                      Staging
                    </button>
                    <button
                      onClick={() => pickEnvironment("production")}
                      className={cn(
                        "flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all",
                        environment === "production"
                          ? "border-success/50 bg-success/10 text-success"
                          : "border-border bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Circle className={cn("h-2 w-2 inline mr-2", environment === "production" ? "fill-success text-success" : "fill-muted-foreground text-muted-foreground")} />
                      Production
                    </button>
                  </div>
                </div>
              </div>

              {selectedSupportsDualPat() && (
                <div className="text-center">
                  <button
                    type="button"
                    onClick={switchToOAuthAuth}
                    className="text-xs text-blue-400 hover:text-blue-300 underline-offset-2 hover:underline"
                  >
                    Connect with OAuth instead
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
        </div>

        <DialogFooter className="shrink-0 mt-0 px-6 py-4 border-t border-border bg-card">
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          {step === "configure" && (
            <Button 
              onClick={handleConnect} 
              disabled={!canSubmitApiKey() || isCreating}
              className="gap-2"
            >
              {isCreating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <Key className="h-4 w-4" />
                  {selectedType === "GitHub"
                    ? "Connect with personal access token"
                    : selectedType === "Zendesk"
                      ? "Connect with API token"
                      : "Connect with API Key"}
                </>
              )}
            </Button>
          )}
          {step === "webhook" && (
            <Button 
              onClick={handleConnect} 
              disabled={!name || isCreating}
              className="gap-2"
            >
              {isCreating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4" />
                  Verify Connection
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function GaPropertyPickerModal({
  connectorId,
  open,
  onClose,
  onLinked,
}: {
  connectorId: string
  open: boolean
  onClose: () => void
  onLinked: () => void
}) {
  const [properties, setProperties] = useState<
    Array<{ property_id: string; display_name?: string; account_name?: string }>
  >([])
  const [selectedId, setSelectedId] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open || !connectorId) return
    startTransition(() => setLoading(true))
    connectorsApi
      .listGoogleAnalyticsProperties(connectorId)
      .then((res) => {
        setProperties(res.properties || [])
        const linked = res.linkedPropertyId
        if (linked) setSelectedId(linked)
        else if (res.properties?.length === 1) setSelectedId(res.properties[0].property_id)
      })
      .catch((err) => {
        console.error("[connectors] GA properties:", err)
        toast.error("Could not load GA4 properties")
      })
      .finally(() => setLoading(false))
  }, [open, connectorId])

  const handleLink = async () => {
    if (!selectedId) return
    const prop = properties.find((p) => p.property_id === selectedId)
    setSaving(true)
    try {
      await connectorsApi.linkGoogleAnalyticsProperty(connectorId, {
        propertyId: selectedId,
        propertyName: prop?.display_name,
      })
      toast.success("GA4 property linked")
      onLinked()
      onClose()
    } catch (err) {
      console.error("[connectors] GA property link:", err)
      toast.error("Failed to link property")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link GA4 property</DialogTitle>
          <DialogDescription>
            Choose which Google Analytics 4 property this connector should use for reports.
          </DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading properties…
          </div>
        ) : properties.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            No GA4 properties found for this Google account.
          </p>
        ) : (
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            <option value="">Select a property…</option>
            {properties.map((p) => (
              <option key={p.property_id} value={p.property_id}>
                {p.display_name || p.property_id}
                {p.account_name ? ` (${p.account_name})` : ""}
              </option>
            ))}
          </select>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleLink} disabled={!selectedId || saving || loading}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Link property"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function GscSitePickerModal({
  connectorId,
  open,
  onClose,
  onLinked,
}: {
  connectorId: string
  open: boolean
  onClose: () => void
  onLinked: () => void
}) {
  const [sites, setSites] = useState<Array<{ site_url: string; permission_level?: string }>>([])
  const [selectedUrl, setSelectedUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open || !connectorId) return
    startTransition(() => setLoading(true))
    connectorsApi
      .listGoogleSearchConsoleSites(connectorId)
      .then((res) => {
        setSites(res.sites || [])
        const linked = res.linkedSiteUrl
        if (linked) setSelectedUrl(linked)
        else if (res.sites?.length === 1) setSelectedUrl(res.sites[0].site_url)
      })
      .catch((err) => {
        console.error("[connectors] GSC sites:", err)
        toast.error("Could not load Search Console sites")
      })
      .finally(() => setLoading(false))
  }, [open, connectorId])

  const handleLink = async () => {
    if (!selectedUrl) return
    const site = sites.find((s) => s.site_url === selectedUrl)
    setSaving(true)
    try {
      await connectorsApi.linkGoogleSearchConsoleSite(connectorId, {
        siteUrl: selectedUrl,
        permissionLevel: site?.permission_level,
      })
      toast.success("Search Console site linked")
      onLinked()
      onClose()
    } catch (err) {
      console.error("[connectors] GSC site link:", err)
      toast.error("Failed to link site")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link Search Console site</DialogTitle>
          <DialogDescription>
            Choose which Google Search Console property this connector should use for search analytics.
            This is separate from Google Analytics — connecting GA4 does not grant Search Console access.
          </DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading sites…
          </div>
        ) : sites.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            No Search Console sites found for this Google account.
          </p>
        ) : (
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={selectedUrl}
            onChange={(e) => setSelectedUrl(e.target.value)}
          >
            <option value="">Select a site…</option>
            {sites.map((s) => (
              <option key={s.site_url} value={s.site_url}>
                {s.site_url}
                {s.permission_level ? ` (${s.permission_level})` : ""}
              </option>
            ))}
          </select>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleLink} disabled={!selectedUrl || saving || loading}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Link site"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function GoogleAdsCustomerPickerModal({
  connectorId,
  open,
  onClose,
  onLinked,
}: {
  connectorId: string
  open: boolean
  onClose: () => void
  onLinked: () => void
}) {
  const [customers, setCustomers] = useState<Array<{ customer_id: string; resource_name?: string }>>([])
  const [selectedId, setSelectedId] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open || !connectorId) return
    startTransition(() => setLoading(true))
    connectorsApi
      .listGoogleAdsCustomers(connectorId)
      .then((res) => {
        setCustomers(res.customers || [])
        const linked = res.linkedCustomerId
        if (linked) setSelectedId(String(linked))
        else if (res.customers?.length === 1) setSelectedId(res.customers[0].customer_id)
      })
      .catch((err) => {
        console.error("[connectors] Google Ads customers:", err)
        toast.error("Could not load Google Ads customers", {
          description:
            "Confirm GOOGLE_ADS_DEVELOPER_TOKEN is set on the API and your Google account can access Ads.",
        })
      })
      .finally(() => setLoading(false))
  }, [open, connectorId])

  const handleLink = async () => {
    if (!selectedId) return
    setSaving(true)
    try {
      await connectorsApi.linkGoogleAdsCustomer(connectorId, { customerId: selectedId })
      toast.success("Google Ads customer linked")
      onLinked()
      onClose()
    } catch (err) {
      console.error("[connectors] Google Ads customer link:", err)
      toast.error("Failed to link Google Ads customer")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link Google Ads customer</DialogTitle>
          <DialogDescription>
            Choose which Google Ads account this connector should use. Google Ads also requires a
            developer token on the API (Manager account → Tools → API Center → Developer token).
            That is separate from Google OAuth and is usually the slowest setup step.
          </DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading customers…
          </div>
        ) : customers.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            No Google Ads customers found for this Google account. Confirm the account has Ads access
            and that the API developer token is approved.
          </p>
        ) : (
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            <option value="">Select a customer…</option>
            {customers.map((c) => (
              <option key={c.customer_id} value={c.customer_id}>
                {c.customer_id}
              </option>
            ))}
          </select>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleLink} disabled={!selectedId || saving || loading}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Link customer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ConnectorsPageContent() {
  const { user } = useAuth()
  const { isAdmin: orgIsAdmin } = useOrgAdmin()
  const router = useRouter()
  const searchParams = useSearchParams()
  const consumedConnectPreset = useRef<string | null>(null)
  const [gaPropertyPicker, setGaPropertyPicker] = useState<{ connectorId: string } | null>(null)
  const [gscSitePicker, setGscSitePicker] = useState<{ connectorId: string } | null>(null)
  const [adsCustomerPicker, setAdsCustomerPicker] = useState<{ connectorId: string } | null>(null)
  const [orgId, setOrgId] = useState<string | null>(() => getQuickOrgId())

  useEffect(() => {
    if (user) void ensureSelectedOrg(true).then(setOrgId)
  }, [user])

  const [searchQuery, setSearchQuery] = useState("")
  const [configureModal, setConfigureModal] = useState<Connector | null>(null)
  const [deleteModal, setDeleteModal] = useState<Connector | null>(null)
  const [addModal, setAddModal] = useState(false)
  const [addModalPreset, setAddModalPreset] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<"topology" | "grid">("topology")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")
  const [isLiveRefreshing, setIsLiveRefreshing] = useState(false)

  const connectorsKey = user && orgId ? `/api/connectors?org=${orgId}` : null

  // Fetch connectors from API with SWR (org-scoped key avoids stale cross-device cache)
  const { data, error, isLoading, isValidating, mutate } = useSWR<{ connectors: Connector[] }>(
    connectorsKey,
    apiFetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000, onError: (err) => console.error("[connectors] fetch error:", err) }
  )

  const refreshLiveStatus = async () => {
    if (!orgId) return
    setIsLiveRefreshing(true)
    try {
      const live = await apiFetcher<{ connectors: Connector[] }>(`/api/connectors?org=${orgId}&live=1`)
      await mutate(live, { revalidate: false })
    } catch (err) {
      console.error("[connectors] live status refresh failed:", err)
      toast.error("Live status check failed", {
        description: formatUnknownError(err, "Could not refresh OAuth token validity."),
      })
    } finally {
      setIsLiveRefreshing(false)
    }
  }

  const { data: registryData } = useSWR<{
    connectors: Array<{
      name: string
      vendor: string
      description: string
      authType: "oauth" | "apiKey"
      certificationBadge?: string | null
    }>
  }>(
    user && orgId ? `/api/marketplace/registry?org=${orgId}` : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )

  const publishedConnectors = registryData?.connectors ?? []
  const partnerVendorKeys = useMemo(
    () => new Set(publishedConnectors.map((entry) => connectorVendorKey(entry.vendor))),
    [publishedConnectors],
  )
  const connectors = useMemo(
    () =>
      normalizeConnectorsResponse(data).filter((connector) =>
        shouldShowConnectedConnectorOnHub(
          connector.vendorKey,
          connector.config,
          partnerVendorKeys,
          connector.rawStatus,
        ),
      ),
    [data, partnerVendorKeys],
  )
  const isAdmin = orgIsAdmin

  useEffect(() => {
    const connectPreset =
      searchParams.get("type") || searchParams.get("connect") || searchParams.get("vendor")
    if (!connectPreset || consumedConnectPreset.current === connectPreset) return
    consumedConnectPreset.current = connectPreset
    setAddModalPreset(connectPreset)
    setAddModal(true)
    const params = new URLSearchParams(searchParams.toString())
    params.delete("type")
    params.delete("connect")
    params.delete("vendor")
    const qs = params.toString()
    router.replace(qs ? `/connectors?${qs}` : "/connectors", { scroll: false })
  }, [searchParams, router])

  useEffect(() => {
    const oauth = searchParams.get("oauth")
    const provider = searchParams.get("provider")
    const connectorId = searchParams.get("connectorId")
    const selectProperty = searchParams.get("selectProperty")
    const selectSite = searchParams.get("selectSite")
    const selectCustomer = searchParams.get("selectCustomer")
    if (!oauth) return
    if (oauth === "success") {
      void mutate()
      if (provider === "google_analytics" && selectProperty === "1" && connectorId) {
        startTransition(() => setGaPropertyPicker({ connectorId }))
        toast.info("Select a GA4 property", {
          description: "Your Google account has multiple analytics properties.",
        })
      } else if (provider === "google_search_console" && selectSite === "1" && connectorId) {
        startTransition(() => setGscSitePicker({ connectorId }))
        toast.info("Select a Search Console site", {
          description: "Your Google account has multiple Search Console properties.",
        })
      } else if (provider === "google_ads" && selectCustomer === "1" && connectorId) {
        startTransition(() => setAdsCustomerPicker({ connectorId }))
        toast.info("Select a Google Ads customer", {
          description:
            "Your Google account can access multiple Ads accounts, or a developer token is still required.",
        })
      } else {
        toast.success("Connection successful", {
          description: provider
            ? `${formatVendorLabel(provider)} is now connected`
            : "OAuth authentication completed",
        })
      }
    } else if (oauth === "error") {
      const message = searchParams.get("message")
      toast.error("OAuth connection failed", { description: message || "Try again or contact support" })
    }
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href)
      url.searchParams.delete("oauth")
      url.searchParams.delete("provider")
      url.searchParams.delete("connectorId")
      url.searchParams.delete("message")
      url.searchParams.delete("selectProperty")
      url.searchParams.delete("selectSite")
      url.searchParams.delete("selectCustomer")
      window.history.replaceState({}, "", url.pathname + url.search)
    }
  }, [searchParams, mutate])

  const handleSync = async (connectorId: string) => {
    const previousConnectors = connectors
    await mutate(
      {
        connectors: previousConnectors.map((c) =>
          c.id === connectorId ? { ...c, status: "syncing", lastSync: "Syncing..." } : c
        ),
      },
      false
    )

    try {
      await connectorsApi.sync(connectorId)
      toast.success("Sync initiated")
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to sync connector:", err)
      await mutate({ connectors: previousConnectors }, false)
      toast.error("Failed to initiate sync")
    }
  }

  const handleSaveConfig = async (connectorId: string, config: Connector["config"]) => {
    const previousConnectors = connectors
    await mutate(
      {
        connectors: previousConnectors.map((c) => (c.id === connectorId ? { ...c, config } : c)),
      },
      false
    )

    try {
      const updatePayload: Record<string, unknown> = {}
      if (config?.apiKey?.trim()) updatePayload.apiKey = config.apiKey.trim()
      if (config?.webhookUrl) updatePayload.webhookUrl = config.webhookUrl
      if (config?.syncInterval) updatePayload.syncFrequency = config.syncInterval
      const { apiKey: _omitKey, syncInterval: _omitSync, ...configRest } = config || {}
      if (Object.keys(configRest).length > 0) updatePayload.config = configRest
      await connectorsApi.update(connectorId, updatePayload)
      toast.success("Configuration saved")
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to save connector config:", err)
      await mutate({ connectors: previousConnectors }, false)
      toast.error("Failed to save configuration", {
        description: err instanceof Error ? err.message : "Please try again",
      })
    }
  }

  const handleDeleteConnector = async (connectorId: string, confirmName: string) => {
    const previousConnectors = connectors
    await mutate({ connectors: previousConnectors.filter((c) => c.id !== connectorId) }, false)

    try {
      await connectorsApi.delete(connectorId, confirmName)
      toast.success("Connector removed")
      await mutate()
    } catch (err) {
      console.error("[connectors] Failed to delete connector:", err)
      await mutate({ connectors: previousConnectors }, false)
      toast.error("Failed to remove connector", {
        description: err instanceof Error ? err.message : "Please try again",
      })
    }
  }

  const handleReconnectOAuth = async (connector: Connector) => {
    const provider = connectorVendorKey(connector.type)
    const cfg = connector.config ?? {}
    const extra: { subdomain?: string; instanceUrl?: string; owner?: string; repo?: string } = {}
    if (cfg.subdomain) extra.subdomain = String(cfg.subdomain)
    if (cfg.instance_url) extra.instanceUrl = String(cfg.instance_url)
    if (cfg.owner) extra.owner = String(cfg.owner)
    if (cfg.repo) extra.repo = String(cfg.repo)
    try {
      const { authorizationUrl } = await connectorsApi.reconnectOAuth(
        provider,
        connector.id,
        connector.name,
        extra
      )
      window.location.assign(authorizationUrl)
    } catch (err) {
      console.error("[connectors] OAuth reconnect failed:", err)
      toast.error("Failed to start OAuth", {
        description: err instanceof Error ? err.message : `${connector.type} OAuth may not be configured`,
      })
    }
  }

  const handleTestConnection = async (connectorId: string) => {
    try {
      const result = await connectorsApi.testConnection(connectorId)
      if (result.success) {
        toast.success("Connection successful")
        await mutate()
      } else {
        toast.error(result.message || "Connection test failed")
      }
    } catch (err) {
      console.error("[v0] Connection test failed:", err)
      toast.error("Connection test failed")
    }
  }

  const filteredConnectors = connectors.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.type.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === "all" || c.status === statusFilter
    const matchesCategory = categoryFilter === "all" || c.category === categoryFilter
    return matchesSearch && matchesStatus && matchesCategory
  })

  const leftConnectors = filteredConnectors.filter((_, i) => i % 2 === 0)
  const rightConnectors = filteredConnectors.filter((_, i) => i % 2 === 1)

  const connectedCount = connectors.filter((c) => connectorIsExecutable(c)).length
  const connectedVendorKeys = useMemo(
    () => new Set(connectors.map((c) => connectorVendorKey(c.type))),
    [connectors],
  )
  const availableToConnect = useMemo(
    () =>
      listAvailableConnectors().filter(
        (entry) => !connectedVendorKeys.has(entry.vendorKey),
      ),
    [connectedVendorKeys],
  )
  const hasActiveFilters = Boolean(
    searchQuery.trim() || statusFilter !== "all" || categoryFilter !== "all",
  )
  const hubConnectedCount = hasActiveFilters
    ? filteredConnectors.filter((c) => connectorIsExecutable(c)).length
    : connectedCount
  const hubTotalCount = hasActiveFilters ? filteredConnectors.length : connectors.length

  function clearFilters() {
    setSearchQuery("")
    setStatusFilter("all")
    setCategoryFilter("all")
  }

  function openAddModal(preset?: string | null) {
    setAddModalPreset(preset ?? null)
    setAddModal(true)
  }

  function closeAddModal() {
    setAddModal(false)
    setAddModalPreset(null)
  }

  const statusFilterOptions = [
    { value: "all", label: "All", color: "text-foreground" },
    { value: "connected", label: "Connected", color: "text-success", dot: "bg-emerald-500" },
    { value: "syncing", label: "Syncing", color: "text-blue-400", dot: "bg-blue-500" },
    { value: "error", label: "Error", color: "text-destructive", dot: "bg-red-500" },
    { value: "disconnected", label: "Offline", color: "text-muted-foreground", dot: "bg-muted-foreground" },
  ] as const
  const totalRequests = connectors.reduce((sum, c) => sum + (c.requestsToday || 0), 0)
  const avgLatency = Math.round(
    connectors.filter((c) => c.latency).reduce((sum, c) => sum + (c.latency || 0), 0) /
    connectors.filter((c) => c.latency).length || 0
  )

  return (
    <AppShell title={SURFACE_COPY.pages.connectors.title}>
      <div className="flex flex-col h-full min-h-0">
        {/* Header */}
        <div className="border-b border-border px-4 md:px-6 py-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3 md:gap-4">
              {/* Brand gradient + theme-aware ring, matching PageHeader's icon
                  chip. Was off-brand blue/violet with a blue ring. */}
              <div className="flex h-9 w-9 md:h-10 md:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 ring-1 ring-border">
                <Cable className="h-4 w-4 md:h-5 md:w-5 text-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-foreground">{SURFACE_COPY.pages.connectors.headline}</h1>
                <p className="text-xs md:text-sm text-muted-foreground">{SURFACE_COPY.pages.connectors.description}</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2 md:gap-3">
              <div className="relative flex-1 md:flex-none">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search connectors..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full md:w-64 pl-9 bg-secondary"
                />
              </div>
              {/* Mobile / tablet filters (desktop pills are lg+) */}
              <div className="flex lg:hidden items-center gap-2 w-full overflow-x-auto pb-1">
                {statusFilterOptions.map((status) => (
                  <button
                    key={status.value}
                    onClick={() => setStatusFilter(status.value)}
                    className={cn(
                      // rounded-full to match the lg+ desktop pills above: this is the
                      // same filter control at a smaller breakpoint, so it must not
                      // change shape.
                      "flex shrink-0 items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all border",
                      statusFilter === status.value
                        ? "bg-card shadow-sm text-foreground border-border"
                        : "text-muted-foreground border-transparent hover:text-foreground",
                    )}
                  >
                    {"dot" in status && status.dot ? (
                      <div className={cn("h-1.5 w-1.5 rounded-full", status.dot)} />
                    ) : null}
                    {status.label}
                  </button>
                ))}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="h-8 shrink-0 gap-1.5 text-xs">
                      <Filter className="h-3.5 w-3.5" />
                      {categoryFilter !== "all" ? categoryFilter.split(" / ")[0] : "Category"}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuItem onClick={() => setCategoryFilter("all")} className="gap-2">
                      <LayoutGrid className="h-4 w-4 text-muted-foreground" />
                      All Categories
                      {categoryFilter === "all" && <Check className="h-3.5 w-3.5 ml-auto text-blue-400" />}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    {Object.entries(connectorCategories).map(([cat, data]) => (
                      <DropdownMenuItem key={cat} onClick={() => setCategoryFilter(cat)} className="gap-2">
                        <span className="flex-1">{cat}</span>
                        <span className="text-[10px] text-muted-foreground">{data.connectors.length}</span>
                        {categoryFilter === cat && <Check className="h-3.5 w-3.5 ml-1 text-blue-400" />}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                {hasActiveFilters ? (
                  <Button variant="ghost" size="sm" className="h-8 shrink-0 text-xs" onClick={clearFilters}>
                    Clear
                  </Button>
                ) : null}
              </div>
              {/* Status Filter Pills */}
              <div className="hidden lg:flex items-center gap-1 border rounded-lg p-1 bg-secondary/30">
                {statusFilterOptions.map((status) => (
                  <button
                    key={status.value}
                    onClick={() => setStatusFilter(status.value)}
                    className={cn(
                      "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all",
                      statusFilter === status.value 
                        ? "bg-card shadow-sm text-foreground" 
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {"dot" in status && status.dot ? (
                      <div className={cn("h-1.5 w-1.5 rounded-full", status.dot)} />
                    ) : null}
                    {status.label}
                  </button>
                ))}
              </div>

              {/* Category Dropdown - Now cleaner */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-9 gap-2 hidden md:flex">
                    <Filter className="h-3.5 w-3.5" />
                    {categoryFilter !== "all" ? categoryFilter.split(" / ")[0] : "Category"}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuItem 
                    onClick={() => setCategoryFilter("all")}
                    className="gap-2"
                  >
                    <LayoutGrid className="h-4 w-4 text-muted-foreground" />
                    All Categories
                    {categoryFilter === "all" && <Check className="h-3.5 w-3.5 ml-auto text-blue-400" />}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  {Object.entries(connectorCategories).map(([cat, data]) => {
                    const colorMap: Record<string, string> = {
                      emerald: "text-success",
                      blue: "text-blue-400",
                      violet: "text-violet-400",
                      amber: "text-warning",
                      pink: "text-pink-400",
                      cyan: "text-cyan-400",
                      orange: "text-orange-400",
                      indigo: "text-indigo-400",
                    }
                    return (
                      <DropdownMenuItem 
                        key={cat} 
                        onClick={() => setCategoryFilter(cat)}
                        className="gap-2"
                      >
                        <div className={cn("h-2 w-2 rounded-full", `bg-${data.color}-500`)} />
                        <span className="flex-1">{cat}</span>
                        <span className="text-[10px] text-muted-foreground">{data.connectors.length}</span>
                        {categoryFilter === cat && <Check className="h-3.5 w-3.5 ml-1 text-blue-400" />}
                      </DropdownMenuItem>
                    )
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
              <div className="hidden md:flex border rounded-md" role="group" aria-label="Connector view mode">
                <Button 
                  variant={viewMode === "topology" ? "secondary" : "ghost"} 
                  size="sm" 
                  className="h-9 w-9 p-0 rounded-r-none"
                  onClick={() => setViewMode("topology")}
                  aria-label="Network topology view"
                  aria-pressed={viewMode === "topology"}
                >
                  <Cable className="h-4 w-4" />
                </Button>
                <Button 
                  variant={viewMode === "grid" ? "secondary" : "ghost"} 
                  size="sm" 
                  className="h-9 w-9 p-0 rounded-l-none"
                  onClick={() => setViewMode("grid")}
                  aria-label="Grid view"
                  aria-pressed={viewMode === "grid"}
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
              </div>
              {/* Secondary actions collapsed into an overflow menu to keep the
                  toolbar from overflowing. These are navigation links, so a
                  dropdown is the natural home for them. */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-9 w-9 p-0 shrink-0" aria-label="More options">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem asChild>
                    <Link href="/marketplace/billing" className="gap-2">
                      <Receipt className="h-4 w-4 text-muted-foreground" />
                      Partner billing
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/marketplace/submit" className="gap-2">
                      <Code2 className="h-4 w-4 text-muted-foreground" />
                      Partner SDK
                    </Link>
                  </DropdownMenuItem>
                  {isAdmin && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem asChild>
                        <Link href="/marketplace/admin" className="gap-2">
                          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                          Review submissions
                        </Link>
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 shrink-0"
                onClick={() => openAddModal()}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Browse all</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 shrink-0"
                disabled={isLiveRefreshing || isValidating || !orgId}
                onClick={() => void refreshLiveStatus()}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", (isLiveRefreshing || isValidating) && "animate-spin")} />
                <span className="hidden sm:inline">Check live status</span>
              </Button>
              <Button onClick={() => openAddModal()} className="gap-2 shrink-0">
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">Add Connector</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Live Stats Bar */}
        <div className="border-b border-border bg-secondary/30 px-4 md:px-6 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-4 md:gap-8">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs md:text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{connectedCount}</span> connected
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Zap className="h-3.5 w-3.5 text-warning" />
                <span className="text-xs md:text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{totalRequests.toLocaleString()}</span> <span className="hidden sm:inline">requests</span> today
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-blue-500" />
                <span className="text-xs md:text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{avgLatency}ms</span> <span className="hidden sm:inline">avg</span> latency
                </span>
              </div>
            </div>
            <div className="hidden md:flex items-center gap-2 text-xs text-muted-foreground">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live monitoring active
            </div>
          </div>
        </div>

        {/* Recommended connectors (AI-driven, from usage signals) */}
        <ConnectorRecommendations onConnect={(type) => openAddModal(type)} />

        <AvailableConnectorsStrip
          entries={availableToConnect}
          onBrowseAll={() => openAddModal()}
          onSelect={(type) => openAddModal(type)}
          showBrowseAll={false}
        />

        {/* Network Topology View */}
        <div className="flex-1 p-4 md:p-6 overflow-auto">
          {connectors.length > 0 && (
            <div className="mb-4 flex justify-end">
              <DataFreshness
                updatedAt={data ? Date.now() : null}
                isRefreshing={isValidating || isLiveRefreshing}
                onRefresh={() => void refreshLiveStatus()}
              />
            </div>
          )}
          {isLoading && connectors.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <Spinner size="lg" className="mb-4" />
              <p className="text-sm text-muted-foreground">Loading connectors...</p>
            </div>
          ) : error && connectors.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <XCircle className="h-10 w-10 text-destructive mb-4" />
              <h3 className="text-base font-medium text-foreground mb-1">Unable to load connectors</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {formatUnknownError(error, "Check backend connectivity and try again.")}
              </p>
              <Button variant="outline" onClick={() => mutate()}>Try again</Button>
            </div>
          ) : connectors.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary mb-4">
                <Cable className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-base font-medium text-foreground mb-1">No connectors yet</h3>
              <p className="text-sm text-muted-foreground mb-4 max-w-sm">
                Connect your CRM, analytics, and productivity tools to power workflows and agents.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={isLiveRefreshing || isValidating || !orgId}
                onClick={() => void refreshLiveStatus()}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", (isLiveRefreshing || isValidating) && "animate-spin")} />
                Check live status
              </Button>
              <Button onClick={() => openAddModal()} className="gap-2">
                <Plus className="h-4 w-4" />
                Add your first connector
              </Button>
              {availableToConnect.length > 0 && (
                <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-lg">
                  {availableToConnect.slice(0, 6).map((entry) => (
                    <Button
                      key={entry.vendorKey}
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => openAddModal(entry.type)}
                    >
                      <ConnectorIcon vendor={entry.type} size="xs" showStatusIndicator={false} />
                      {entry.type}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          ) : filteredConnectors.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center px-4">
              <Filter className="h-10 w-10 text-muted-foreground/50 mb-3" />
              <p className="text-sm font-medium text-foreground">No connectors match your filters</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                {connectors.length} connector{connectors.length === 1 ? "" : "s"} are hidden by search or filter settings.
              </p>
              <Button variant="outline" size="sm" className="mt-4" onClick={clearFilters}>
                Clear filters
              </Button>
            </div>
          ) : (
          <>
          {/* Mobile: Card list view */}
          <div className="md:hidden space-y-4">
            {/* Mobile Hub Summary */}
            <div className="flex items-center justify-center py-4">
              <div className="relative">
                <div className="absolute -inset-2 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 blur-lg" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-card to-secondary border-2 border-blue-500/30 shadow-xl">
                  <div className="text-center">
                    <Cable className="h-5 w-5 text-blue-400 mx-auto mb-0.5" />
                    <div className="text-lg font-bold text-foreground">{hubConnectedCount}</div>
                    <div className="text-[8px] text-muted-foreground uppercase tracking-wider">
                      of {hubTotalCount}
                      {hasActiveFilters ? " shown" : ""}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Mobile connector cards */}
            <div className="space-y-3">
              {filteredConnectors.map((connector) => (
                <ConnectorNode
                  key={connector.id}
                  connector={connector}
                  position="right"
                  onConfigure={() => setConfigureModal(connector)}
                  onSync={handleSync}
                  onTestConnection={handleTestConnection}
                  onReconnect={handleReconnectOAuth}
                  onDelete={() => setDeleteModal(connector)}
                />
              ))}
            </div>
          </div>

          {/* Desktop: Network topology view */}
          {viewMode === "topology" && (
            <div className="hidden md:block relative min-h-[600px]">
              <div className="flex items-center justify-center">
                {/* Left column */}
                <div className="flex flex-col gap-4 mr-8">
                  {leftConnectors.map((connector) => (
                    <ConnectorNode
                      key={connector.id}
                      connector={connector}
                      position="left"
                      onConfigure={() => setConfigureModal(connector)}
                      onSync={handleSync}
                      onTestConnection={handleTestConnection}
                  onReconnect={handleReconnectOAuth}
                      onDelete={() => setDeleteModal(connector)}
                    />
                  ))}
                </div>

                {/* Central Hub */}
                <CentralHub connectedCount={hubConnectedCount} totalCount={hubTotalCount} />

                {/* Right column */}
                <div className="flex flex-col gap-4 ml-8">
                  {rightConnectors.map((connector) => (
                    <ConnectorNode
                      key={connector.id}
                      connector={connector}
                      position="right"
                      onConfigure={() => setConfigureModal(connector)}
                      onSync={handleSync}
                      onTestConnection={handleTestConnection}
                  onReconnect={handleReconnectOAuth}
                      onDelete={() => setDeleteModal(connector)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Desktop: Grid view */}
          {viewMode === "grid" && (
            <div className="hidden md:grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredConnectors.map((connector) => (
                <ConnectorNode
                  key={connector.id}
                  connector={connector}
                  position="right"
                  onConfigure={() => setConfigureModal(connector)}
                  onSync={handleSync}
                  onTestConnection={handleTestConnection}
                  onReconnect={handleReconnectOAuth}
                  onDelete={() => setDeleteModal(connector)}
                />
              ))}
            </div>
          )}
          </>
          )}
        </div>

        {/* Modals */}
        {configureModal && (
          <ConfigureModal
            connector={configureModal}
            open={!!configureModal}
            onClose={() => setConfigureModal(null)}
            onSave={handleSaveConfig}
            onReconnectOAuth={handleReconnectOAuth}
          />
        )}
        {deleteModal && (
          <DeleteModal
            connector={deleteModal}
            open={!!deleteModal}
            onClose={() => setDeleteModal(null)}
            onConfirm={handleDeleteConnector}
          />
        )}
        <AddConnectorModal
          open={addModal}
          onClose={closeAddModal}
          initialConnectorType={addModalPreset}
          existingConnectors={connectors}
          publishedConnectors={publishedConnectors}
          onCreated={async () => {
            await mutate()
          }}
        />
        {gaPropertyPicker && (
          <GaPropertyPickerModal
            connectorId={gaPropertyPicker.connectorId}
            open
            onClose={() => setGaPropertyPicker(null)}
            onLinked={() => void mutate()}
          />
        )}
        {gscSitePicker && (
          <GscSitePickerModal
            connectorId={gscSitePicker.connectorId}
            open
            onClose={() => setGscSitePicker(null)}
            onLinked={() => void mutate()}
          />
        )}
        {adsCustomerPicker && (
          <GoogleAdsCustomerPickerModal
            connectorId={adsCustomerPicker.connectorId}
            open
            onClose={() => setAdsCustomerPicker(null)}
            onLinked={() => void mutate()}
          />
        )}
      </div>
    </AppShell>
  )
}

function ConnectorsPageFallback() {
  return (
    <AppShell title={SURFACE_COPY.pages.connectors.title}>
      <div className="flex h-[50vh] items-center justify-center">
        <Spinner size="lg" />
      </div>
    </AppShell>
  )
}

export default function ConnectorsPage() {
  return (
    <Suspense fallback={<ConnectorsPageFallback />}>
      <ConnectorsPageContent />
    </Suspense>
  )
}
