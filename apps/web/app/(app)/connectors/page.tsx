"use client"

// Connectors Page - Integration Hub with Network Topology View
import { Suspense, startTransition, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR, { mutate as globalMutate } from "swr"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Illustration } from "@/components/gravitre/illustration"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { ConnectorRecommendations } from "@/components/connectors/connector-recommendations"
import { AvailableConnectorsStrip } from "@/components/connectors/available-connectors-strip"
import { OutboundProviderCards } from "@/components/connectors/outbound-provider-cards"
import { DATA_REMOVAL_KEY, DataRemovalReceipts } from "@/components/connectors/data-removal"
import { EnterpriseKnowledgeSync } from "@/components/settings/enterprise-knowledge-sync"
import "@/components/settings/settings-kit.css"
import "@/components/settings/enterprise-sections.css"
import {
  deriveConnectorAttention,
  useAgentsByVendor,
  useVendorCapabilities,
  type ConnectorAgentRef,
  type ConnectorAttention,
  type VendorCapability,
} from "@/components/connectors/connector-operating"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Input } from "@/components/ui/input"
import { toast } from "@/components/connectors/overlays/toast"
import { ConnectorsOverlaysProvider } from "@/components/connectors/overlays/connectors-overlays"
import { ConfigureConnectorDialog, RemoveConnectorDialog, type ConfigurePatch, type DialogConnector } from "@/components/connectors/redesign/connector-dialogs"
import { usageSentence, usePlays, useWorkflows } from "@/components/connectors/redesign/connector-usage"
import {
  AttentionCard,
  CapabilityFabric,
  FirstRun,
  HubFilters,
  HubHero,
  HubInspector,
  HubSideSummary,
  KnowledgeCard,
  SystemsTable,
  accessLabel,
  exportRowsCsv,
  hubStatusOf,
  useStarterSets,
  type FabricPhase,
  type HubRow,
  type HubStatusFilter,
} from "@/components/connectors/redesign/hub"
import "@/components/workspace/workspace.css"
import "@/components/connectors/redesign/connectors.css"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { coverTypeFor, vendorLook, type CoverType } from "@/components/connectors/redesign/vendor-look"
import { 
  Search,
  RefreshCw,
  Settings,
  Trash2,
  ExternalLink,
  ArrowRight,
  Circle,
  CheckCircle2,
  XCircle,
  Loader2,
  MoreVertical,
  Eye,
  EyeOff,
  Wifi,
  WifiOff,
  Cable,
  Globe,
  Key,
  Link2,
  Copy,
  Check,
  X as XIcon,
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
import { openManagedConnector, managedProviderAvailable } from "@/lib/managed-connector-auth"
import { reconnectConnector, type ReconnectTarget } from "@/components/connectors/redesign/reconnect"
import { isManagedConnectorVendor, MANAGED_OAUTH_FALLBACK_VENDOR_KEYS } from "@/lib/connectors"
import { openPlaidLink } from "@/lib/plaid-link"
import {
  connectorDepartment,
  connectorInDepartment,
  type ConnectorDepartmentId,
} from "@/components/connectors/department-filter"
import type { Connector as ApiConnector } from "@/types/api"

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
  lastSyncAt?: string | null
  createdAt?: string | null
  syncFrequency?: string | null
  recordsSynced?: number | null
  description: string
  category?: string
  authType?: "oauth" | "apiKey" | "webhook"
  authStatus?: string
  blockingReason?: string
  recoveryAction?: string
  availability?: ConnectorAvailability
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
    auth_provider?: string
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
    <div className="mb-3 flex flex-wrap gap-1.5">
      {badges.map(({ label, ok }) => (
        <span
          key={label}
          className={cn(
            "inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-0.5 text-[10px] font-medium capitalize",
            ok
              ? "border-divide text-[color:var(--g-text-secondary)]"
              : "border-divide/70 text-[color:var(--g-text-muted)] opacity-70",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              ok ? "bg-[color:var(--g-brand)]" : "bg-[color:var(--g-text-muted)]",
            )}
            aria-hidden
          />
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
    lastSyncAt: String(model.lastSync ?? model.last_sync ?? model.last_sync_at ?? "") || null,
    createdAt: String(model.createdAt ?? model.created_at ?? "") || null,
    syncFrequency: String(model.syncFrequency ?? model.sync_frequency ?? "") || null,
    recordsSynced: typeof model.recordsSynced === "number" ? model.recordsSynced : null,
    description: String(model.description ?? ""),
    category: String(model.category ?? lookupConnectorCategory(vendor) ?? ""),
    authType: authType === "oauth" || authType === "webhook" ? authType : "apiKey",
    authStatus: authStatus || undefined,
    blockingReason: availability?.blockingReason,
    recoveryAction: availability?.recoveryAction,
    availability,
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
    color: "text-[color:var(--status-verified)]", 
    bg: "bg-[color:var(--status-verified)]", 
    ring: "ring-[color:var(--status-verified)]/30",
    glow: "shadow-[color:var(--status-verified)]/20",
    icon: CheckCircle2,
    label: "Connected" 
  },
  disconnected: { 
    color: "text-muted-foreground", 
    bg: "bg-muted-foreground", 
    ring: "ring-muted-foreground/30",
    glow: "shadow-muted-foreground/10",
    icon: WifiOff,
    label: "Disconnected" 
  },
  error: { 
    color: "text-[color:var(--status-failed)]", 
    bg: "bg-[color:var(--status-failed)]", 
    ring: "ring-[color:var(--status-failed)]/30",
    glow: "shadow-[color:var(--status-failed)]/20",
    icon: XCircle,
    label: "Error" 
  },
  syncing: { 
    color: "text-[color:var(--status-running)]", 
    bg: "bg-[color:var(--status-running)]", 
    ring: "ring-[color:var(--status-running)]/30",
    glow: "shadow-[color:var(--status-running)]/20",
    icon: Loader2,
    label: "Syncing" 
  },
}

/**
 * Topology edge — same Nodus homepage connection-line language as
 * HorizontalLine / RightSideSVG (base --color-line + sweeping blue gradient).
 */
function TopologyConnectionLine({
  active,
  direction = "right",
  className,
}: {
  active: boolean
  direction?: "right" | "left"
  className?: string
}) {
  const reactId = useId()
  const gradientId = `gv-conn-edge-${reactId.replace(/:/g, "")}`
  const sweepFromLeft = direction === "right"

  return (
    <svg
      aria-hidden
      viewBox="0 0 314 2"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="none"
      className={cn("h-[2px] w-full min-w-[4rem] flex-1", className)}
    >
      <line
        x1="0.5"
        y1="1"
        x2="313.5"
        y2="1"
        stroke="var(--color-line)"
        strokeLinecap="round"
      />
      {active ? (
        <>
          <line
            x1="0.5"
            y1="1"
            x2="313.5"
            y2="1"
            stroke={`url(#${gradientId})`}
            strokeLinecap="round"
          />
          <defs>
            <motion.linearGradient
              id={gradientId}
              gradientUnits="userSpaceOnUse"
              initial={{
                y1: 0,
                y2: 1,
                x1: sweepFromLeft ? "-10%" : "110%",
                x2: sweepFromLeft ? "0%" : "120%",
              }}
              animate={{
                y1: 0,
                y2: 1,
                x1: sweepFromLeft ? "110%" : "-10%",
                x2: sweepFromLeft ? "120%" : "0%",
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                repeatType: "loop",
                ease: "easeInOut",
                repeatDelay: 1,
              }}
            >
              <stop stopColor="var(--color-line)" />
              <stop offset="0.5" stopColor="var(--color-info)" />
              <stop offset="1" stopColor="var(--color-line)" />
            </motion.linearGradient>
          </defs>
        </>
      ) : null}
    </svg>
  )
}

/** Central hub — Nodus NativeToolsHubLogo rings + count, with Connected badge. */
function CentralHub({ connectedCount, totalCount }: { connectedCount: number; totalCount: number }) {
  return (
    <div className="relative flex flex-col items-center gap-3">
      <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-md bg-muted p-px shadow-xl sm:h-24 sm:w-24">
        <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-info)_20%,transparent_30%)]" />
        <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [animation-delay:1s] [animation-duration:2s] [background-image:conic-gradient(at_center,transparent,var(--color-brand)_20%,transparent_30%)]" />
        <div className="relative z-20 flex h-full w-full flex-col items-center justify-center rounded-[5px] bg-card p-2 text-foreground">
          <Cable className="mb-0.5 h-5 w-5 text-[color:var(--color-brand)] sm:h-6 sm:w-6" />
          <div className="text-lg font-bold leading-none sm:text-xl">{connectedCount}</div>
          <div className="text-[9px] text-muted-foreground sm:text-[10px]">
            of {totalCount}
          </div>
        </div>
      </div>
      <span className="rounded-sm border border-success/30 bg-success/10 px-2 py-0.5 text-xs text-success">
        Connected
      </span>
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
  onFocus,
  variant = "topology",
}: { 
  connector: Connector
  position: "left" | "right"
  onConfigure: () => void
  onSync: (connectorId: string) => Promise<void>
  onTestConnection: (connectorId: string) => Promise<void>
  onReconnect?: (connector: Connector) => Promise<void>
  onDelete: () => void
  onFocus?: (connector: Connector) => void
  variant?: "topology" | "list"
}) {
  const isSyncing = connector.status === "syncing"

  const optionsMenu = (
    <ConnectorOptionsMenu
      connector={connector}
      onConfigure={onConfigure}
      onSync={onSync}
      onTestConnection={onTestConnection}
      onReconnect={onReconnect}
      onDelete={onDelete}
    />
  )

  if (variant === "list") {
    return (
      <div className="flex items-center gap-3 border-b border-divide py-2.5" data-gravitre-connector-row="">
        <ConnectorIcon
          vendor={connector.type}
          status={connector.status === "syncing" ? "syncing" : connector.status === "connected" ? "connected" : connector.status === "error" ? "error" : "disconnected"}
          size="sm"
          showStatusIndicator={false}
        />
        <button
          type="button"
          className="min-w-0 flex-1 text-left"
          onClick={() => onFocus?.(connector)}
        >
          <p className="truncate text-sm font-medium text-foreground">{connector.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">
            {connector.type}
            {" · "}
            {isSyncing ? "Syncing" : connectorStatusLabel(connector)}
          </p>
        </button>
        {optionsMenu}
      </div>
    )
  }

  return <ConnectorTopologyCard connector={connector} position={position} optionsMenu={optionsMenu} onReconnect={onReconnect} />
}

function ConnectorOptionsMenu({
  connector,
  onConfigure,
  onSync,
  onTestConnection,
  onReconnect,
  onDelete,
}: {
  connector: Connector
  onConfigure: () => void
  onSync: (connectorId: string) => Promise<void>
  onTestConnection: (connectorId: string) => Promise<void>
  onReconnect?: (connector: Connector) => Promise<void>
  onDelete: () => void
}) {
  const isSyncing = connector.status === "syncing"
  const handleSync = async () => {
    await onSync(connector.id)
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="-my-2 h-11 w-11 shrink-0" aria-label={`${connector.name} options`}>
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
          Sync now
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => void onTestConnection(connector.id)}>
          <Wifi className="h-3.5 w-3.5 mr-2" />
          Test connection
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
  )
}

function ConnectorTopologyCard({
  connector,
  position,
  optionsMenu,
  onReconnect,
}: {
  connector: Connector
  position: "left" | "right"
  optionsMenu: ReactNode
  onReconnect?: (connector: Connector) => Promise<void>
}) {
  const [isHovered, setIsHovered] = useState(false)
  const config = statusConfig[connector.status] ?? statusConfig.disconnected
  const StatusIcon = config.icon
  const isSyncing = connector.status === "syncing"

  return (
    <motion.div
      initial={{ opacity: 0, x: position === "left" ? -20 : 20 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "group relative w-full max-w-md",
        position === "left" ? "flex-row-reverse" : "flex-row"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Connection line */}
      <div className={cn(
        "flex w-full items-center gap-2",
        position === "left" ? "flex-row-reverse" : "flex-row"
      )}>
        {/* Node */}
        <div className={cn(
          "relative w-full shrink-0 rounded-[var(--np-radius-lg)] border bg-[color:var(--g-surface-1)] p-3 shadow-[var(--np-shadow)] transition-all duration-300 md:max-w-[280px] md:min-w-[240px] md:p-4",
          isHovered ? "border-[color:var(--g-border-active)]" : "border-divide",
          connector.status === "connected" && "shadow-[var(--g-brand-glow)]",
          connector.status === "error" && "border-destructive/30"
        )}>
          {/* Status indicator — inset (not corner-overhang) so it cannot read as window chrome */}
          <div
            className={cn(
              "absolute right-2.5 top-2.5 flex h-5 w-5 items-center justify-center rounded-full",
              config.bg,
            )}
            title={config.label}
            aria-hidden
          >
            {isSyncing ? (
              <Loader2 className="h-2.5 w-2.5 text-background animate-spin" />
            ) : (
              <StatusIcon className="h-2.5 w-2.5 text-background" />
            )}
          </div>

          {/* Header */}
          <div className="mb-3 flex items-start justify-between gap-2 pr-8">
            <div className="flex min-w-0 items-center gap-3">
              <ConnectorIcon 
                vendor={connector.type} 
                status={connector.status === "syncing" ? "syncing" : connector.status === "connected" ? "connected" : connector.status === "error" ? "error" : "disconnected"}
                size="sm"
                showStatusIndicator={false}
              />
              <div className="min-w-0">
                <h3 className="truncate text-sm font-medium text-foreground">{connector.name}</h3>
                <p className="text-[10px] text-muted-foreground">{connector.type}</p>
              </div>
            </div>
            
            <div className="shrink-0 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 focus-within:opacity-100">
              {optionsMenu}
            </div>
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
                    className="text-[10px] text-[color:var(--g-emerald-deep)] hover:text-primary transition-colors"
                    onClick={() => void onReconnect(connector)}
                  >
                    {connector.authStatus === "auth_expired" ? "Reconnect OAuth" : "Complete OAuth"}
                  </button>
                )}
              <Link 
                href={`/connectors/${connector.id}`}
                className="text-[10px] text-[color:var(--g-emerald-deep)] hover:text-primary transition-colors"
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

        {/* Nodus-style connection line — hidden on mobile */}
        <div className="hidden min-w-[6rem] flex-1 items-center md:flex md:max-w-[12rem] lg:min-w-[8rem] lg:max-w-[16rem]">
          <TopologyConnectionLine
            active={connectorIsExecutable(connector)}
            direction={position === "left" ? "right" : "left"}
          />
        </div>
      </div>
    </motion.div>
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

type PickChipId = "suggested" | "all" | "crm" | "helpdesk" | "finance" | "marketing" | "docs"

/** The add flow's kind-of-system chips, matched on the same cover types as the detail page. */
const PICK_CHIPS: Array<{ id: PickChipId; label: string; covers?: CoverType[] }> = [
  { id: "suggested", label: "Suggested" },
  { id: "all", label: "All" },
  { id: "crm", label: "CRM", covers: ["crm", "data"] },
  { id: "helpdesk", label: "Helpdesk", covers: ["helpdesk", "chat"] },
  { id: "finance", label: "Finance", covers: ["accounting", "erp"] },
  { id: "marketing", label: "Marketing", covers: ["marketing", "email"] },
  { id: "docs", label: "Docs", covers: ["docs", "projects"] },
]

function getSelectedConnectorKey(catalog: CatalogConnector[], type: string): string {
  const entry = catalog.find((c) => c.type === type)
  return entry?.vendorKey || type
}

function PickCard({ entry, note, disabled, onPick }: { entry: CatalogConnector; note: string; disabled?: boolean; onPick: () => void }) {
  const look = vendorLook(entry.vendorKey || entry.type, entry.category)
  return (
    <button type="button" className="cno-pick" aria-disabled={disabled ? "true" : undefined} onClick={onPick} title={entry.description}>
      <span className="cno-tile mono" style={{ background: look.bg, color: look.fg }} aria-hidden>
        {look.mono}
      </span>
      <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <span className="t">{entry.type}</span>
        <span className="s">{note}</span>
      </span>
    </button>
  )
}

// Add Connector Modal
function AddConnectorModal({
  open,
  onClose,
  onCreated,
  existingConnectors,
  publishedConnectors = [],
  initialConnectorType = null,
  capabilities,
  agentsByVendor,
}: {
  open: boolean
  onClose: () => void
  onCreated: () => Promise<void>
  existingConnectors: Connector[]
  capabilities?: Map<string, VendorCapability>
  agentsByVendor?: Map<string, ConnectorAgentRef[]>
  publishedConnectors?: Array<{
    name: string
    vendor: string
    description: string
    authType: "oauth" | "apiKey"
    certificationBadge?: string | null
  }>
  initialConnectorType?: string | null
}) {
  const router = useRouter()
  const { data: managedCatalog } = useSWR(open ? "managed-connector-catalog" : null, connectorsApi.managedCatalog)
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
  const [twilioAccountSid, setTwilioAccountSid] = useState("")
  const [twilioAuthToken, setTwilioAuthToken] = useState("")

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

  const [pickChip, setPickChip] = useState<PickChipId>("all")
  const connectedKeys = useMemo(
    () => new Set(existingConnectors.map((c) => connectorVendorKey(c.vendorKey || c.type))),
    [existingConnectors],
  )
  // Systems your agents already name in their setup but nothing is connected for yet, most used first.
  const suggestedConnectors = useMemo(() => {
    const out: Array<{ entry: CatalogConnector; agents: number }> = []
    for (const entry of catalogConnectors) {
      if (entry.partner || !isShippedConnector(entry)) continue
      const key = connectorVendorKey(entry.vendorKey || entry.type)
      if (connectedKeys.has(key)) continue
      const agents = agentsByVendor?.get(key)?.length ?? 0
      if (agents > 0) out.push({ entry, agents })
    }
    return out.sort((a, b) => b.agents - a.agents).slice(0, 6)
  }, [catalogConnectors, connectedKeys, agentsByVendor])
  useEffect(() => {
    if (open) setPickChip(suggestedConnectors.length > 0 ? "suggested" : "all")
    // Only when the dialog opens; the person's own chip choice stays after that.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const managedLabel = (connector: CatalogConnector): string => {
    const key = connector.vendorKey || connector.type
    if (!managedProviderAvailable(managedCatalog, key)) {
      return managedCatalog?.connectors.find((entry) => entry.vendor === key)?.setupReason === "interactive_oauth_unavailable"
        ? "Sign-in unavailable"
        : "Setup required"
    }
    return connector.shipped ? "Actions supported" : "Connect account"
  }
  const pickAvailable = (connector: CatalogConnector): boolean =>
    !connector.partner && !isPartnerGatedConnector(connector) && isShippedConnector(connector)
  const pickNote = (connector: CatalogConnector): string => {
    if (connector.partner) return connector.certified ? "Partner · Certified" : "Partner connector"
    if (isPartnerGatedConnector(connector)) return "Request access"
    if (!isShippedConnector(connector)) return "Coming soon"
    const auth =
      connector.authType === "oauth"
        ? isManagedConnectorVendor(connector.vendorKey || connector.type)
          ? "Secure sign in"
          : "OAuth"
        : connector.authType === "webhook"
          ? "Webhook"
          : "API key"
    const state = isManagedConnectorVendor(connector.vendorKey || connector.type) ? managedLabel(connector) : "Available"
    const linked = connectedKeys.has(connectorVendorKey(connector.vendorKey || connector.type)) ? " · connected" : ""
    return `${auth} · ${state}${linked}`
  }
  const selectedCapability = selectedType
    ? capabilities?.get(connectorVendorKey(getSelectedConnectorKey(catalogConnectors, selectedType)))
    : undefined

  const resolveVendor = (connector: CatalogConnector | undefined, type: string) =>
    connector?.vendorKey || connectorVendorKey(type)

  // Webhook URL for webhook-based connectors
  const webhookUrl = `${publicApiUrl()}/webhooks/${selectedType?.toLowerCase().replace(/\s+/g, "-")}/incoming`

  const filteredModalConnectors = catalogConnectors.filter((c) => {
    const matchesSearch = c.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.category.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = modalCategoryFilter === "all" || c.category === modalCategoryFilter
    const chip = PICK_CHIPS.find((x) => x.id === pickChip)
    const matchesChip = !chip?.covers || chip.covers.includes(coverTypeFor(c.vendorKey || c.type, c.category))
    return matchesSearch && matchesCategory && matchesChip
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

  const handleOAuthConnect = async (managedFallback = false) => {
    if (!selectedType || !canStartOAuth()) return
    const selected = getSelectedConnector()
    const provider = resolveVendor(selected, selectedType)
    const existing = existingConnectors.find(
      (c) =>
        connectorVendorKey(c.type) === provider ||
        c.name.trim().toLowerCase() === name.trim().toLowerCase()
    )

    if (isManagedConnectorVendor(provider) || managedFallback || existing?.config?.auth_provider === "managed") {
      setSelectedEnvironmentInStorage(environment)
      setOauthStatus("redirecting")
      try {
        const connected = await openManagedConnector(provider, { name, connectorId: existing?.id })
        setOauthStatus(connected ? "success" : "idle")
        if (connected) {
          toast.success(`${selectedType} connected`)
          await onCreated()
          onClose()
        }
      } catch (err) {
        setOauthStatus("error")
        toast.error(`Failed to connect ${selectedType}`, { description: oauthErrorMessage(err, selectedType) })
      }
      return
    }

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
    if (selectedType === "Twilio") {
      return Boolean(apiKey.trim() && apiSecret.trim())
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
        sync_frequency: "1h",
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
      } else if (selectedType === "Twilio") {
        payload.config = {
          ...(twilioAccountSid.trim() ? { account_sid: twilioAccountSid.trim() } : {}),
        }
        payload.secrets = {
          api_key_sid: apiKey.trim(),
          api_key_secret: apiSecret.trim(),
          ...(twilioAuthToken.trim() ? { auth_token: twilioAuthToken.trim() } : {}),
        }
      } else if (apiKey) {
        payload.api_key = apiKey
        ;(payload as { apiKey?: string }).apiKey = apiKey
      }
      const created = await connectorsApi.create(payload)
      const createdId = created && typeof created === "object" ? String((created as { id?: unknown }).id ?? "") : ""
      // Run the real connection test straight away so the toast says whether agents can use it.
      let test: { success: boolean; message?: string } | null = null
      if (createdId) {
        try {
          test = await connectorsApi.testConnection(createdId)
        } catch (err) {
          test = { success: false, message: err instanceof Error ? err.message : undefined }
        }
      }
      const openIt = createdId
        ? { label: "Open connector", onClick: () => router.push(`/connectors/${createdId}`) }
        : undefined
      if (!test || test.success) {
        toast.success(`${selectedType} is ready for agents`, {
          vendor: vendor,
          topic: "Connected",
          description: test ? "Saved, and the connection test passed." : "Saved. Run a test from the connector to confirm access.",
          action: openIt,
        })
      } else {
        toast.warning(`${selectedType} was saved, but the test failed`, {
          vendor: vendor,
          topic: "Connection test",
          description: test.message || "Check the credentials, then test again from the connector.",
          action: openIt,
        })
      }
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
    setPickChip("all")
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
    setTwilioAccountSid("")
    setTwilioAuthToken("")
    onClose()
  }

  const handleSelectConnector = (connector: CatalogConnector) => {
    if (isManagedConnectorVendor(connector.vendorKey || connector.type) && !managedProviderAvailable(managedCatalog, connector.vendorKey || connector.type)) {
      const mode = managedCatalog?.connectors.find((entry) => entry.vendor === (connector.vendorKey || connector.type))?.authMode
      const unsupported = mode && !["OAUTH1", "OAUTH2", "API_KEY"].includes(mode)
      toast.message(unsupported ? "Provider sign-in unavailable" : "Provider setup required", { description: unsupported
        ? "This provider does not yet support the sign-in connection offered by Gravitre."
        : "Gravitre must finish this provider’s authorization setup before accounts can connect." })
      return
    }
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
    if (isManagedConnectorVendor(connector.vendorKey || connector.type) || connector.authType === "oauth") {
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
  }, [open, initialConnectorType, catalogConnectors, managedCatalog])

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(next) => (next ? null : handleClose())} modal={oauthStatus !== "redirecting"}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="cno-scrim" />
        <DialogPrimitive.Content className="cno-dialog wide" aria-describedby={undefined}>
          <div className="cno-dialog-head">
            {selectedType && step !== "select" ? (
              <span className="cno-tile mono" style={{ background: vendorLook(selectedType).bg, color: vendorLook(selectedType).fg }} aria-hidden>
                {vendorLook(selectedType).mono}
              </span>
            ) : null}
            <div className="cno-dialog-heading">
              <DialogPrimitive.Title className="cno-dialog-title">
                {step === "select" ? "Add a connector" : `Connect ${selectedType}`}
              </DialogPrimitive.Title>
              <div className="cno-steps" aria-label="Steps">
                <span data-on={step === "select" ? "" : undefined}>1 Choose a system</span>
                <i aria-hidden />
                <span data-on={step !== "select" ? "" : undefined}>
                  2 {step === "oauth" ? "Sign in" : step === "webhook" ? "Point the webhook" : "Add credentials"}
                </span>
                <i aria-hidden />
                <span>3 Ready for agents</span>
              </div>
            </div>
            <DialogPrimitive.Close className="cno-x filled" aria-label="Close">
              <XIcon size={14} strokeWidth={2.4} aria-hidden />
            </DialogPrimitive.Close>
          </div>
        <div className="cno-dialog-body" style={{ paddingTop: 12 }}>
        <AnimatePresence mode="wait">
          {step === "select" ? (
            <motion.div
              key="select"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              style={{ display: "flex", flexDirection: "column", gap: 14 }}
            >
              <label className="cno-stored" style={{ background: "transparent", padding: "0 12px" }}>
                <Search size={16} aria-hidden />
                <input
                  aria-label="Search systems"
                  placeholder={`Search ${catalogConnectors.length}+ systems`}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ flex: 1, minWidth: 0, border: 0, outline: "none", background: "transparent", font: "inherit", fontSize: 15, color: "inherit" }}
                />
              </label>
              <div className="cno-chips" role="group" aria-label="Kind of system">
                {PICK_CHIPS.filter((chip) => chip.id !== "suggested" || suggestedConnectors.length > 0).map((chip) => (
                  <button key={chip.id} type="button" className="cno-chip" aria-pressed={pickChip === chip.id} onClick={() => setPickChip(chip.id)}>
                    {chip.label}
                  </button>
                ))}
              </div>
              {pickChip === "suggested" && !searchQuery.trim() ? (
                <>
                  <span className="cno-label">Suggested for your agents</span>
                  <div className="cno-picks">
                    {suggestedConnectors.map(({ entry, agents }) => (
                      <PickCard key={entry.type} entry={entry} note={`${agents} ${agents === 1 ? "agent uses" : "agents use"} it`} onPick={() => handleSelectConnector(entry)} />
                    ))}
                  </div>
                </>
              ) : (
                <div className="cno-scroll" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {Object.keys(groupedConnectors).length === 0 ? (
                    <div className="cno-note info">
                      <span style={{ flex: 1 }}>No systems match. Try another name, or browse partner connectors.</span>
                      <button type="button" className="cno-btn ghost xs" onClick={() => { setSearchQuery(""); setPickChip("all") }}>
                        Clear
                      </button>
                    </div>
                  ) : (
                    Object.entries(groupedConnectors).map(([category, connectors]) => (
                      <div key={category} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        <span className="cno-label">{category}</span>
                        <div className="cno-picks">
                          {connectors.map((connector) => (
                            <PickCard key={connector.type} entry={connector} note={pickNote(connector)} disabled={!pickAvailable(connector)} onPick={() => handleSelectConnector(connector)} />
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
              <Link href="/marketplace/connectors" className="cno-btn line sm" style={{ alignSelf: "flex-start" }} onClick={() => handleClose()}>
                Browse partner connectors <ArrowRight size={14} aria-hidden />
              </Link>
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
                    <span className="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-[color:var(--g-emerald-deep)] font-medium">{isManagedConnectorVendor(selectedConnectorMeta()?.vendorKey || "") ? "Secure authorization" : "OAuth"}</span>
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
                    <div className="mx-auto h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
                      <Globe className="h-8 w-8 text-[color:var(--g-emerald-deep)]" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">Connect with {selectedType}</h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        {isManagedConnectorVendor(selectedConnectorMeta()?.vendorKey || "")
                          ? `Sign in with ${selectedType} and approve access for Gravitre.`
                          : <>You&apos;ll be redirected to {selectedType} to authorize Gravitre</>}
                      </p>
                      {selectedConnectorMeta()?.vendorKey &&
                        PKCE_OAUTH_VENDOR_KEYS.has(selectedConnectorMeta()!.vendorKey!) && (
                          <p className="text-[11px] text-muted-foreground mt-2">
                            Uses secure PKCE authorization (required by {selectedType}).
                          </p>
                        )}
                    </div>
                    {MANAGED_OAUTH_FALLBACK_VENDOR_KEYS.has(selectedConnectorMeta()?.vendorKey || "") && (
                      <Button variant="link" size="sm" disabled={!canStartOAuth() || !managedProviderAvailable(managedCatalog, selectedConnectorMeta()?.vendorKey || "")}
                        onClick={() => void handleOAuthConnect(true)}>
                        {managedProviderAvailable(managedCatalog, selectedConnectorMeta()?.vendorKey || "") ? "Connect securely with provider" : "Provider sign-in needs platform setup"}
                      </Button>
                    )}
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
                            className="inline-flex items-center gap-1 text-xs text-[color:var(--g-emerald-deep)] hover:text-primary"
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
                    {selectedCapability && selectedCapability.actions.length > 0 ? (
                      <div className="text-left max-w-sm mx-auto" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        <span className="cno-label">What Gravitre will be able to do</span>
                        <ul className="cno-can">
                          {selectedCapability.actions.slice(0, 5).map((action) => (
                            <li key={action.id}>
                              <Check size={15} aria-hidden />
                              <span>
                                {action.name}
                                {action.requiresApproval ? " · asks first" : ""}
                              </span>
                            </li>
                          ))}
                        </ul>
                        {selectedCapability.actions.length > 5 ? (
                          <span className="cno-hint">
                            and {selectedCapability.actions.length - 5} more. Writes stay off until you turn on actions.
                          </span>
                        ) : (
                          <span className="cno-hint">Writes stay off until you turn on actions.</span>
                        )}
                      </div>
                    ) : null}
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
                  <div className="flex flex-col items-center gap-4 rounded-[10px] border border-divide bg-secondary/20 px-6 py-8 text-center shadow-[var(--elevation-1)]">
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
                  <div className="flex flex-col items-center gap-4 rounded-[10px] border border-[color:var(--g-emerald)]/25 bg-primary/5 px-6 py-8 text-center shadow-[var(--elevation-1)]">
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
                  <div className="flex flex-col items-center gap-4 rounded-[10px] border border-destructive/20 bg-card px-6 py-8 text-center shadow-[var(--elevation-2)]">
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
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-[color:var(--g-signal-surface)] text-[color:var(--g-signal)] uppercase font-medium">Webhook</span>
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
                  <Link2 className="h-4 w-4 text-[color:var(--g-signal)]" />
                  Webhook endpoint
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
                <h4 className="text-sm font-medium text-foreground">Setup instructions</h4>
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
                  <label className="text-sm font-medium text-foreground">Connector name</label>
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
                    <span className="text-xs px-1.5 py-0.5 rounded bg-warning/10 text-warning font-medium">API Key</span>
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
                  <label className="text-sm font-medium text-foreground">Connector name</label>
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
                        className="inline-flex items-center gap-1 text-xs text-[color:var(--g-emerald-deep)] hover:text-primary"
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

                {selectedType === "Twilio" && (
                  <>
                    <div className="rounded-lg border border-border bg-secondary/40 p-3 space-y-2">
                      <p className="text-xs text-muted-foreground">
                        Twilio powers PSTN voice (outbound/inbound calls) and SMS. Use an API Key (SK…) + secret from
                        Twilio Console → Account → API keys. Account SID (AC…) is auto-resolved when left blank.
                        Optional Auth Token enables webhook signature verification on inbound PSTN calls.
                      </p>
                      <a
                        href="https://www.twilio.com/docs/iam/api-keys"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-[color:var(--g-emerald-deep)] hover:text-primary"
                      >
                        Twilio API keys guide
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Account SID (optional)</label>
                      <Input
                        value={twilioAccountSid}
                        onChange={(e) => setTwilioAccountSid(e.target.value)}
                        placeholder="ACxxxxxxxx (auto-resolved from API key if blank)"
                        className="bg-secondary font-mono text-sm"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-foreground">Optional auth token</label>
                      <Input
                        type="password"
                        value={twilioAuthToken}
                        onChange={(e) => setTwilioAuthToken(e.target.value)}
                        placeholder="Primary Auth Token — optional; for inbound webhook verification"
                        className="bg-secondary font-mono text-sm"
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
                              : selectedType === "Twilio"
                                ? "API Key SID (SK…)"
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
                {(selectedType === "Stripe" || selectedType === "AWS S3" || selectedType === "Twilio") && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      {selectedType === "AWS S3"
                        ? "Secret Access Key"
                        : selectedType === "Twilio"
                          ? "API Key Secret"
                          : "API Secret"}{" "}
                      {selectedType === "Twilio" ? "" : "(Optional)"}
                    </label>
                    <Input
                      type="password"
                      value={apiSecret}
                      onChange={(e) => setApiSecret(e.target.value)}
                      placeholder={
                        selectedType === "AWS S3"
                          ? "Enter your secret access key"
                          : selectedType === "Twilio"
                            ? "Paste API Key secret from Twilio Console"
                            : "Enter API secret"
                      }
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
                    className="text-xs text-[color:var(--g-emerald-deep)] hover:text-primary underline-offset-2 hover:underline"
                  >
                    Connect with OAuth instead
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
        </div>

        <div className="cno-dialog-foot">
          {step !== "select" ? (
            <button type="button" className="cno-btn ghost" style={{ marginRight: "auto" }} onClick={() => setStep("select")} disabled={oauthStatus === "redirecting" || isCreating}>
              Back
            </button>
          ) : (
            <span className="cno-foot-note">Nothing writes to your apps until you turn on actions.</span>
          )}
          <button type="button" className="cno-btn ghost" onClick={handleClose}>Cancel</button>
          {step === "configure" && (
            <button type="button" className="cno-btn dark" onClick={handleConnect} disabled={!canSubmitApiKey() || isCreating}>
              {isCreating ? <Loader2 size={16} className="cno-spin" aria-hidden /> : null}
              {isCreating ? "Saving and testing" : "Save connector"}
            </button>
          )}
          {step === "webhook" && (
            <button type="button" className="cno-btn dark" onClick={handleConnect} disabled={!name || isCreating}>
              {isCreating ? <Loader2 size={16} className="cno-spin" aria-hidden /> : null}
              {isCreating ? "Verifying" : "Verify connection"}
            </button>
          )}
          {step === "oauth" && oauthStatus === "idle" && (
            <button type="button" className="cno-btn dark" onClick={() => void handleOAuthConnect()} disabled={!canStartOAuth()}>
              {isPlaidLinkConnector(getSelectedConnector()) ? "Continue to Plaid" : `Continue to ${selectedType}`}
            </button>
          )}
        </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
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
    if (user) void ensureSelectedOrg().then(setOrgId)
  }, [user])

  const [searchQuery, setSearchQuery] = useState("")
  const [configureModal, setConfigureModal] = useState<Connector | null>(null)
  const [deleteModal, setDeleteModal] = useState<Connector | null>(null)
  const [addModal, setAddModal] = useState(false)
  const [addModalPreset, setAddModalPreset] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<"list" | "topology">("list")
  const [statusFilter, setStatusFilter] = useState<HubStatusFilter>("all")
  const [departmentFilter, setDepartmentFilter] = useState<ConnectorDepartmentId | null>(null)
  const [isLiveRefreshing, setIsLiveRefreshing] = useState(false)
  const [checkedAt, setCheckedAt] = useState<number | null>(null)
  const inspectorRef = useRef<HTMLElement | null>(null)
  const [focusedConnector, setFocusedConnector] = useState<Connector | null>(null)
  usePublishGravitreAISelection(
    focusedConnector
      ? { kind: "connector", id: focusedConnector.id, label: focusedConnector.name }
      : null,
  )

  const connectorsKey = user && orgId ? `/api/connectors?org=${orgId}` : null

  // Fetch connectors from API with SWR (org-scoped key avoids stale cross-device cache)
  const { data, error, isLoading, isValidating, mutate } = useSWR<{ connectors: Connector[] }>(
    connectorsKey,
    apiFetcher,
    { revalidateOnFocus: true, revalidateOnReconnect: true, refreshInterval: 30_000, dedupingInterval: 10_000, onError: (err) => console.error("[connectors] fetch error:", err) }
  )

  useEffect(() => {
    if (!data) return
    // The newest availability check the API reports; the fetch time when none reports one.
    const stamps = normalizeConnectorsResponse(data)
      .map((c) => (c.availability?.lastCheckedAt ? new Date(c.availability.lastCheckedAt).getTime() : NaN))
      .filter((t) => Number.isFinite(t))
    setCheckedAt(stamps.length ? Math.max(...stamps) : Date.now())
  }, [data])

  const refreshLiveStatus = async () => {
    if (!orgId) return
    setIsLiveRefreshing(true)
    try {
      const live = await apiFetcher<{ connectors: Connector[] }>(`/api/connectors?org=${orgId}&live=1`)
      await mutate(live, { revalidate: false })
      setCheckedAt(Date.now())
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

    let cancelled = false
    const finish = () => {
      if (cancelled || typeof window === "undefined") return
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

    void (async () => {
      if (oauth === "success") {
        try {
          await mutate()
        } catch {
          // Keep oauth=success in the URL so a 401 does not immediately
          // treat this as a dead session (shared Google login client).
        }
        if (cancelled) return
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
      finish()
    })()

    return () => {
      cancelled = true
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

  const handleReconnectOAuth = (connector: Connector) =>
    reconnectConnector(connector as ReconnectTarget, () => mutate())

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

  const handleConfigure = async (connector: Connector, patch: ConfigurePatch): Promise<boolean> => {
    try {
      await connectorsApi.update(connector.id, patch as Record<string, unknown>)
      toast.success(`${connector.name} settings saved`, {
        vendor: connector.vendorKey || connector.type,
        topic: "Configuration",
        description: patch.apiKey ? "The new key is stored encrypted. Run a test to confirm it works." : undefined,
        action: patch.apiKey ? { label: "Test now", onClick: () => void handleTestConnection(connector.id) } : undefined,
      })
      await mutate()
      return true
    } catch (err) {
      toast.error(`Could not save ${connector.name}`, {
        vendor: connector.vendorKey || connector.type,
        topic: "Configuration",
        description: connectorErrorMessage(err),
      })
      return false
    }
  }

  const handleRemove = async (connector: Connector, confirmName: string): Promise<boolean> => {
    const previous = connectors
    try {
      await connectorsApi.delete(connector.id, confirmName)
      await mutate({ connectors: previous.filter((c) => c.id !== connector.id) }, false)
      setFocusedConnector((current) => (current?.id === connector.id ? null : current))
      toast.success(`${connector.name} removed`, {
        vendor: connector.vendorKey || connector.type,
        topic: "Removed",
        description: "Agents and workflows no longer use it. A removal receipt is listed below when data removal runs.",
      })
      void globalMutate(DATA_REMOVAL_KEY)
      await mutate()
      return true
    } catch (err) {
      toast.error(`Could not remove ${connector.name}`, {
        vendor: connector.vendorKey || connector.type,
        topic: "Remove",
        description: connectorErrorMessage(err),
      })
      return false
    }
  }

  const vendorCapabilities = useVendorCapabilities(Boolean(user && orgId))
  const agentsByVendor = useAgentsByVendor(Boolean(user && orgId))
  const plays = usePlays(Boolean(user && orgId))
  const workflowUsage = useWorkflows(Boolean(user && orgId))
  const starterSets = useStarterSets(agentsByVendor)

  const attentionAll = useMemo(
    () => connectors.map((c) => deriveConnectorAttention(c)).filter((x): x is ConnectorAttention => x !== null),
    [connectors],
  )
  const attentionIds = useMemo(() => new Set(attentionAll.map((x) => x.connector.id)), [attentionAll])
  const statusOf = (c: Connector) => hubStatusOf(c, attentionIds.has(c.id))

  const departmentConnectors = useMemo(
    () => connectors.filter((c) => connectorInDepartment(c.category, departmentFilter)),
    [connectors, departmentFilter],
  )
  const searched = departmentConnectors.filter((c) => {
    const q = searchQuery.trim().toLowerCase()
    return !q || c.name.toLowerCase().includes(q) || c.type.toLowerCase().includes(q)
  })
  const statusCounts: Record<HubStatusFilter, number> = { all: searched.length, connected: 0, syncing: 0, attention: 0, offline: 0 }
  for (const c of searched) statusCounts[statusOf(c)] += 1
  const filteredConnectors = searched.filter((c) => statusFilter === "all" || statusOf(c) === statusFilter)
  const attentionItems = attentionAll.filter((item) => filteredConnectors.some((c) => c.id === item.connector.id))

  const selectedConnector = focusedConnector ? connectors.find((c) => c.id === focusedConnector.id) ?? null : null
  const connectedCount = connectors.filter((c) => connectorIsExecutable(c)).length
  const syncingCount = connectors.filter((c) => c.status === "syncing").length
  const connectedVendorKeys = useMemo(() => new Set(connectors.map((c) => connectorVendorKey(c.type))), [connectors])
  const availableToConnect = useMemo(
    () => listAvailableConnectors().filter((entry) => !connectedVendorKeys.has(entry.vendorKey)),
    [connectedVendorKeys],
  )

  // Plays that only wait on one of the systems in the attention list.
  const playsUnlocked = useMemo(() => {
    const keys = new Set<string>()
    for (const item of attentionItems) for (const key of plays.waitingOn.get(item.connector.vendorKey) ?? []) keys.add(key)
    return keys.size
  }, [attentionItems, plays.waitingOn])
  const blockedCount = attentionItems.filter((item) => !connectorIsExecutable(item.connector as Connector)).length
  const unlockLine = [
    blockedCount > 0 ? `Fix ${attentionItems.length === 1 ? "this" : "these"} and ${blockedCount} more ${blockedCount === 1 ? "system" : "systems"} can take actions` : `${attentionItems.length} ${attentionItems.length === 1 ? "system needs" : "systems need"} a person`,
    playsUnlocked > 0 ? `${playsUnlocked} ${playsUnlocked === 1 ? "play unlocks" : "plays unlock"}` : "",
  ]
    .filter(Boolean)
    .join(", and ")

  const usageFor = (c: Connector) => {
    const agents = agentsByVendor.get(c.vendorKey) ?? []
    const workflows = workflowUsage.forVendor(c.vendorKey)
    const vendorPlays = plays.byVendor.get(c.vendorKey) ?? []
    return { agents, workflows, plays: vendorPlays }
  }

  const rows: HubRow[] = filteredConnectors.map((c) => {
    const use = usageFor(c)
    const status = statusOf(c)
    return {
      connector: c,
      status,
      statusLabel: status === "attention" ? connectorStatusLabel(c) : status === "syncing" ? "Syncing" : status === "connected" ? "Connected" : "Offline",
      access: accessLabel(vendorCapabilities.get(c.vendorKey)),
      usedBy: usageSentence(use.agents.length, use.workflows.length, use.plays.length),
    }
  })

  const withAvailability = connectors.filter((c) => c.availability)
  const availabilityCount = (pick: (a: ConnectorAvailability) => boolean): number | null =>
    withAvailability.length === 0 ? null : withAvailability.filter((c) => pick(c.availability!)).length
  const fabric: FabricPhase[] = [
    { id: "systems", label: "Systems added", hint: "In this workspace", count: connectors.length, tone: "neutral" },
    { id: "authorized", label: "Authorized", hint: "Credentials valid", count: availabilityCount((a) => a.authenticated && a.tokenValid), tone: "done" },
    { id: "scoped", label: "Permissions granted", hint: "Required scopes", count: availabilityCount((a) => a.scopesValid), tone: "done" },
    { id: "healthy", label: "Healthy", hint: "Last check passed", count: availabilityCount((a) => a.healthy), tone: "done" },
    { id: "executable", label: "Can take actions", hint: "Agents and workflows can act", count: connectedCount, tone: "live" },
    {
      id: "blocked",
      label: "Blocked",
      hint: "Needs a person",
      count: withAvailability.length === 0 ? null : withAvailability.filter((c) => c.availability!.blockingReason).length,
      tone: "risk",
    },
  ]

  function openAddModal(preset?: string | null) {
    setAddModalPreset(preset ?? null)
    setAddModal(true)
  }

  function closeAddModal() {
    setAddModal(false)
    setAddModalPreset(null)
  }

  function pickFilter(filter: HubStatusFilter) {
    setStatusFilter(filter)
    setViewMode("list")
    if (typeof document !== "undefined") document.getElementById("cn-filters")?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  function inspect(connector: Connector | null) {
    setFocusedConnector(connector)
    if (connector && typeof window !== "undefined" && window.matchMedia("(max-width: 1023px)").matches) {
      window.setTimeout(() => inspectorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50)
    }
  }

  const runAttention = (item: ConnectorAttention) => {
    const target = connectors.find((c) => c.id === item.connector.id)
    if (!target) return
    inspect(target)
    if (item.action === "reconnect") void handleReconnectOAuth(target)
    else if (item.action === "configure") setConfigureModal(target)
    else void handleTestConnection(target.id)
  }

  const dialogConnector = (c: Connector): DialogConnector => ({
    id: c.id,
    name: c.name,
    type: c.type,
    vendorKey: c.vendorKey,
    environment: c.environment,
    authType: c.authType,
    authStatus: c.authStatus,
    maskedApiKey: c.config?.apiKey ?? null,
    authProvider: c.config?.auth_provider ?? null,
    syncFrequency: c.syncFrequency ?? c.config?.syncInterval ?? null,
    blockingReason: c.blockingReason ?? null,
    recordsSynced: c.recordsSynced ?? null,
  })

  const deptLabel = departmentFilter ? connectorDepartment(departmentFilter)?.label : null
  const firstRun = !isLoading && !error && connectors.length === 0
  const removeUsage = deleteModal ? usageFor(deleteModal) : null

  return (
    <AppShell title={SURFACE_COPY.pages.connectors.title}>
      <ConnectorsOverlaysProvider>
        <div className="gv-ws" data-testid="connectors-hub-b" data-composition="manage" style={{ minHeight: "100%", background: "var(--gv-canvas)" }}>
          <div className="cn-page">
            {isLoading && connectors.length === 0 ? (
              <div className="cn-card cn-pad" style={{ alignItems: "center", padding: "72px 18px" }}>
                <Spinner size="lg" />
                <p className="cn-sub">Loading connectors</p>
              </div>
            ) : error && connectors.length === 0 ? (
              <div className="cn-card cn-pad" style={{ alignItems: "center", textAlign: "center", padding: "56px 18px" }}>
                <Illustration name="moment-error" width={170} />
                <h2 className="cn-h2">Unable to load connectors</h2>
                <p className="cn-sub">{formatUnknownError(error, "Check backend connectivity and try again.")}</p>
                <button type="button" className="gv-btn outline" onClick={() => void mutate()}>
                  Try again
                </button>
              </div>
            ) : firstRun ? (
              <FirstRun sets={starterSets} onAdd={(preset) => openAddModal(preset ?? null)} />
            ) : (
              <>
                <HubHero
                  connectors={connectors}
                  readyCount={connectedCount}
                  syncingCount={syncingCount}
                  attentionCount={attentionAll.length}
                  playsWaiting={plays.waiting}
                  playsLoaded={plays.loaded}
                  checkedAt={checkedAt}
                  refreshing={isLiveRefreshing || isValidating}
                  onRefresh={() => void refreshLiveStatus()}
                  onAdd={() => openAddModal()}
                  onFilter={pickFilter}
                />
                <CapabilityFabric phases={fabric} total={connectors.length} />
                <div id="cn-filters" style={{ scrollMarginTop: 80 }}>
                  <HubFilters
                    status={statusFilter}
                    onStatus={setStatusFilter}
                    counts={statusCounts}
                    query={searchQuery}
                    onQuery={setSearchQuery}
                    department={departmentFilter}
                    onDepartment={setDepartmentFilter}
                    view={viewMode}
                    onView={setViewMode}
                  />
                </div>
                {filteredConnectors.length === 0 ? (
                  <div className="cn-card cn-pad" style={{ alignItems: "center", textAlign: "center", padding: "40px 18px" }}>
                    <h2 className="cn-h2">{deptLabel && !searchQuery.trim() && statusFilter === "all" ? `No ${deptLabel} connectors yet` : "No connectors match"}</h2>
                    <p className="cn-sub">
                      {deptLabel && !searchQuery.trim() && statusFilter === "all"
                        ? "Connect a system this team uses, or pick another department."
                        : `${connectors.length} ${connectors.length === 1 ? "connector is" : "connectors are"} hidden by search or filters.`}
                    </p>
                    <div className="cn-row-flex" style={{ justifyContent: "center" }}>
                      <button
                        type="button"
                        className="gv-btn outline sm"
                        onClick={() => {
                          setSearchQuery("")
                          setStatusFilter("all")
                          setDepartmentFilter(null)
                        }}
                      >
                        Clear filters
                      </button>
                      <button type="button" className="gv-btn dark sm" onClick={() => openAddModal()}>
                        Add connector
                      </button>
                    </div>
                  </div>
                ) : viewMode === "topology" ? (
                  <div className="cn-card" style={{ padding: 20, overflowX: "auto" }}>
                    <div className="flex min-w-[720px] items-center justify-center gap-0">
                      <div className="mr-2 flex flex-1 flex-col items-end gap-6">
                        {filteredConnectors
                          .filter((_, i) => i % 2 === 0)
                          .map((connector) => (
                            <ConnectorNode
                              key={connector.id}
                              connector={connector}
                              position="left"
                              onConfigure={() => setConfigureModal(connector)}
                              onSync={handleSync}
                              onTestConnection={handleTestConnection}
                              onReconnect={handleReconnectOAuth}
                              onDelete={() => setDeleteModal(connector)}
                              onFocus={(c) => inspect(c)}
                            />
                          ))}
                      </div>
                      <CentralHub
                        connectedCount={filteredConnectors.filter((c) => connectorIsExecutable(c)).length}
                        totalCount={filteredConnectors.length}
                      />
                      <div className="ml-2 flex flex-1 flex-col items-start gap-6">
                        {filteredConnectors
                          .filter((_, i) => i % 2 === 1)
                          .map((connector) => (
                            <ConnectorNode
                              key={connector.id}
                              connector={connector}
                              position="right"
                              onConfigure={() => setConfigureModal(connector)}
                              onSync={handleSync}
                              onTestConnection={handleTestConnection}
                              onReconnect={handleReconnectOAuth}
                              onDelete={() => setDeleteModal(connector)}
                              onFocus={(c) => inspect(c)}
                            />
                          ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="cn-cols" data-testid="connectors-list-view" data-review-surface="connectors-management">
                    <div className="cn-main">
                      <AttentionCard items={attentionItems} unlock={unlockLine} onAction={runAttention} />
                      <SystemsTable
                        title={deptLabel ? `${deptLabel} connectors` : "Connected systems"}
                        rows={rows}
                        selectedId={selectedConnector?.id ?? null}
                        onSelect={(c) => inspect(selectedConnector?.id === c.id ? null : (c as Connector))}
                        onExport={() => {
                          exportRowsCsv(rows)
                          toast.success(`Exported ${rows.length} ${rows.length === 1 ? "connector" : "connectors"}`, {
                            topic: "Export",
                            description: "The CSV has the rows shown, with your current filters.",
                          })
                        }}
                        menu={(c) => (
                          <ConnectorOptionsMenu
                            connector={c as Connector}
                            onConfigure={() => setConfigureModal(c as Connector)}
                            onSync={handleSync}
                            onTestConnection={handleTestConnection}
                            onReconnect={handleReconnectOAuth}
                            onDelete={() => setDeleteModal(c as Connector)}
                          />
                        )}
                      />
                    </div>
                    <aside className="cn-side" aria-label="Inspector" ref={inspectorRef}>
                      {selectedConnector ? (
                        <HubInspector
                          connector={selectedConnector}
                          statusLabel={connectorStatusLabel(selectedConnector)}
                          capability={vendorCapabilities.get(selectedConnector.vendorKey)}
                          {...usageFor(selectedConnector)}
                          attention={deriveConnectorAttention(selectedConnector)}
                          onReconnect={
                            selectedConnector.authType === "oauth" ? () => void handleReconnectOAuth(selectedConnector) : undefined
                          }
                          onConfigure={() => setConfigureModal(selectedConnector)}
                          onTest={() => handleTestConnection(selectedConnector.id)}
                          onSync={() => handleSync(selectedConnector.id)}
                          onClose={() => setFocusedConnector(null)}
                        />
                      ) : (
                        <HubSideSummary
                          readyCount={connectedCount}
                          total={connectors.length}
                          attention={attentionAll}
                          onPick={(id) => inspect(connectors.find((c) => c.id === id) ?? null)}
                        />
                      )}
                      <KnowledgeCard isAdmin={isAdmin} />
                    </aside>
                  </div>
                )}
              </>
            )}

            {!firstRun ? <DataRemovalReceipts /> : null}
            {isAdmin && !firstRun ? (
              // Full sync status and history; the side card above summarises it.
              <section id="knowledge-sync" aria-labelledby="knowledge-sync-heading" className="gv-set flex scroll-mt-20 flex-col gap-3">
                <h2 id="knowledge-sync-heading" className="cn-h2">
                  Knowledge sync
                </h2>
                <EnterpriseKnowledgeSync isAdmin={isAdmin} />
              </section>
            ) : null}
            {connectors.length > 0 ? (
              <div data-testid="connectors-discovery">
                <ConnectorRecommendations onConnect={(type) => openAddModal(type)} />
                <AvailableConnectorsStrip
                  entries={availableToConnect}
                  onBrowseAll={() => openAddModal()}
                  onSelect={(type) => openAddModal(type)}
                  showBrowseAll={false}
                />
              </div>
            ) : null}
            <OutboundProviderCards />
            <div className="cn-row-flex" style={{ fontSize: 13, color: "var(--gv-muted)" }}>
              <Link href="/marketplace/connectors" className="cn-btn-text sm">
                Partner connectors <ArrowRight size={14} aria-hidden />
              </Link>
              <Link href="/marketplace/billing" className="cn-btn-text sm">
                Partner billing
              </Link>
              <Link href="/marketplace/submit" className="cn-btn-text sm">
                Build a partner connector
              </Link>
              {isAdmin ? (
                <Link href="/marketplace/admin" className="cn-btn-text sm">
                  Review submissions
                </Link>
              ) : null}
            </div>
          </div>

          {configureModal ? (
            <ConfigureConnectorDialog
              connector={dialogConnector(configureModal)}
              open
              onOpenChange={(next) => (next ? null : setConfigureModal(null))}
              onSave={(patch) => handleConfigure(configureModal, patch)}
              onReconnect={
                configureModal.authType === "oauth"
                  ? () => {
                      const target = configureModal
                      setConfigureModal(null)
                      void handleReconnectOAuth(target)
                    }
                  : undefined
              }
              missingScopeNote={(() => {
                const names = (agentsByVendor.get(configureModal.vendorKey) ?? []).map((a) => a.name)
                return names.length ? `needed by ${names.slice(0, 2).join(" and ")}` : null
              })()}
            />
          ) : null}
          {deleteModal && removeUsage ? (
            <RemoveConnectorDialog
              connector={dialogConnector(deleteModal)}
              open
              onOpenChange={(next) => (next ? null : setDeleteModal(null))}
              onRemove={(name) => handleRemove(deleteModal, name)}
              agents={removeUsage.agents.length}
              workflows={removeUsage.workflows.length}
              plays={removeUsage.plays.length}
            />
          ) : null}
          <AddConnectorModal
            open={addModal}
            onClose={closeAddModal}
            initialConnectorType={addModalPreset}
            existingConnectors={connectors}
            publishedConnectors={publishedConnectors}
            capabilities={vendorCapabilities}
            agentsByVendor={agentsByVendor}
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
      </ConnectorsOverlaysProvider>
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
