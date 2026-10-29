"use client"

import { useMemo, useState, type ReactNode } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import useSWR, { mutate as globalMutate } from "swr"
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Check,
  Copy,
  Download,
  KeyRound,
  Loader2,
  MoreHorizontal,
  RefreshCw,
  Trash2,
  Workflow as WorkflowIcon,
  Zap,
} from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { Illustration } from "@/components/gravitre/illustration"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { FreshserviceTriggersPanel } from "@/components/connectors/freshservice-triggers-panel"
import { KnowledgeSyncButton } from "@/components/connectors/knowledge-sync-button"
import { DATA_REMOVAL_KEY } from "@/components/connectors/data-removal"
import { CONNECTOR_DEPARTMENTS } from "@/components/connectors/department-filter"
import {
  deriveConnectorAttention,
  useAgentsByVendor,
  useVendorCapabilities,
  type ConnectorAgentRef,
} from "@/components/connectors/connector-operating"
import { ConnectorsOverlaysProvider } from "@/components/connectors/overlays/connectors-overlays"
import { toast } from "@/components/connectors/overlays/toast"
import { ConnectorCover, VendorTile } from "@/components/connectors/redesign/art"
import {
  ConfigureConnectorDialog,
  RemoveConnectorDialog,
  type ConfigurePatch,
  type DialogConnector,
} from "@/components/connectors/redesign/connector-dialogs"
import {
  SYNC_INTERVALS,
  relativeTime,
  syncIntervalLabel,
  usageSentence,
  usePlays,
  useWorkflows,
  type PlayRef,
} from "@/components/connectors/redesign/connector-usage"
import { StatusPill, hubStatusOf, type HubConnector } from "@/components/connectors/redesign/hub"
import { reconnectConnector } from "@/components/connectors/redesign/reconnect"
import { coverFor } from "@/components/connectors/redesign/vendor-look"
import "@/components/workspace/workspace.css"
import "@/components/connectors/redesign/connectors.css"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Spinner } from "@/components/ui/spinner"
import { fetcher as apiFetcher, formatUnknownError } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { connectorsApi } from "@/lib/api"
import type { CapabilitySnapshot } from "@/lib/capabilities"
import type { ConnectorActionDefinition } from "@/lib/connector-actions"
import {
  OAUTH_VENDOR_KEYS,
  connectorVendorKey,
  formatVendorLabel,
  lookupConnectorCategory,
  resolveConnectorDisplayStatus,
} from "@/lib/connectors"
import type { Workflow } from "@/types/api"

/* ------------------------------------------------------------------ Model */

type DetailConnector = HubConnector & {
  description: string
  recordsSynced: number | null
  syncFrequency: string | null
  webhookUrl: string
  maskedApiKey: string | null
  authProvider: string | null
  rawStatus: string
  credentials: { hasOAuthTokens: boolean; grantedScopes: string[]; tokenExpiresAt: string | null } | null
  config: Record<string, unknown>
}

type ActivityEvent = { id: string; action: string; actorId?: string | null; metadata: Record<string, unknown>; createdAt: string | null }

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {}
}

function str(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

function normalizeDetail(payload: unknown): DetailConnector | null {
  const outer = asRecord(payload)
  const raw = outer.connector && typeof outer.connector === "object" ? asRecord(outer.connector) : outer
  const id = str(raw.id)
  if (!id) return null
  const vendor = str(raw.vendor) || str(raw.type)
  const vendorKey = connectorVendorKey(vendor)
  const config = asRecord(raw.config)
  const authTypeRaw = str(config.authType) || str(config.auth_type) || str(raw.authType)
  const authType: DetailConnector["authType"] =
    authTypeRaw === "oauth" || authTypeRaw === "webhook" ? authTypeRaw : OAUTH_VENDOR_KEYS.has(vendorKey) ? "oauth" : "apiKey"
  const rawStatus = str(raw.status) || "disconnected"
  const authStatus = str(raw.authStatus) || str(raw.auth_status)
  const a = raw.availability && typeof raw.availability === "object" ? asRecord(raw.availability) : null
  const availability = a
    ? {
        configured: Boolean(a.configured),
        authenticated: Boolean(a.authenticated),
        tokenValid: Boolean(a.tokenValid ?? a.token_valid),
        scopesValid: Boolean(a.scopesValid ?? a.scopes_valid),
        healthy: Boolean(a.healthy),
        executable: Boolean(a.executable ?? a.execution_available),
        blockingReason: str(a.blockingReason ?? a.blocking_reason) || undefined,
        lastCheckedAt: str(a.lastCheckedAt ?? a.last_checked_at) || undefined,
      }
    : undefined
  const creds = raw.credentials && typeof raw.credentials === "object" ? asRecord(raw.credentials) : null
  const lastSyncAt = str(raw.lastSync) || str(raw.last_sync_at) || null
  return {
    id,
    name: str(raw.name) || formatVendorLabel(vendor) || "Connector",
    type: formatVendorLabel(vendor || "unknown"),
    vendorKey,
    status: resolveConnectorDisplayStatus(rawStatus, authStatus, str(raw.displayStatus) || str(raw.display_status)),
    rawStatus,
    environment: str(raw.environment) === "staging" ? "staging" : "production",
    lastSync: relativeTime(lastSyncAt),
    lastSyncAt,
    createdAt: str(raw.createdAt) || str(raw.created_at) || null,
    category: str(raw.category) || lookupConnectorCategory(vendor) || "",
    authType,
    authStatus: authStatus || undefined,
    blockingReason: availability?.blockingReason,
    availability,
    description: str(raw.description),
    recordsSynced: typeof raw.recordsSynced === "number" ? raw.recordsSynced : null,
    syncFrequency: str(raw.syncFrequency) || str(raw.sync_frequency) || null,
    webhookUrl: str(config.webhookUrl) || str(config.webhook_url),
    maskedApiKey: str(config.apiKey) || null,
    authProvider: str(config.authProvider) || str(config.auth_provider) || null,
    credentials: creds
      ? {
          hasOAuthTokens: Boolean(creds.hasOAuthTokens),
          grantedScopes: Array.isArray(creds.grantedScopes) ? creds.grantedScopes.map(String) : [],
          tokenExpiresAt: str(creds.tokenExpiresAt) || null,
        }
      : null,
    config,
  }
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Never"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

function formatDate(value: string | null | undefined): string {
  if (!value) return ""
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

/** Same authority levels as Plays: reads observe, approved writes recommend, the rest act. */
function authorityOf(action: ConnectorActionDefinition): { label: "Observe" | "Recommend" | "Act"; cls: string } {
  if (action.kind === "read") return { label: "Observe", cls: "observe" }
  return action.requiresApproval ? { label: "Recommend", cls: "recommend" } : { label: "Act", cls: "act" }
}

const AUDIT_LABELS: Record<string, string> = {
  "connector.created": "Connector added",
  "connector.connected": "Connected",
  "connector.configure": "Settings changed",
  "connector.config.updated": "Settings changed",
  "connector.sync.manual": "Manual sync started",
  "connector.oauth.started": "Sign-in started",
  "connector.oauth.connected": "Signed in",
  "connector.oauth.completed": "Sign-in completed",
  "connector.oauth.reconnect_started": "Reconnect started",
  "connector.oauth.reconnected": "Reconnected",
  "connector.auth.failed": "Authorization failed",
  "connector.approval.decided": "Action approval decided",
  "connector.approval.action_mismatch": "Approval did not match the action",
  "connector.phi_capable.updated": "PHI setting changed",
  "connector.data_purge_planned": "Data removal scheduled",
  "connector.data_purged": "Synced data removed",
  "connector.deleted": "Connector removed",
}

function auditLabel(action: string): string {
  if (AUDIT_LABELS[action]) return AUDIT_LABELS[action]
  const tail = action.replace(/^connector\./, "").replace(/[._]+/g, " ").trim()
  return tail ? tail.charAt(0).toUpperCase() + tail.slice(1) : action
}

function csvCell(value: unknown): string {
  const text = value == null ? "" : typeof value === "string" ? value : JSON.stringify(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function downloadAuditCsv(connector: DetailConnector, events: ActivityEvent[]) {
  const lines = [
    ["time", "event", "action", "actor", "details"].join(","),
    ...events.map((e) => [e.createdAt, auditLabel(e.action), e.action, e.actorId ?? "", e.metadata].map(csvCell).join(",")),
  ]
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${connector.vendorKey || "connector"}-audit-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

/* ------------------------------------------------------------------ Pieces */

type Tab = "overview" | "actions" | "used" | "credentials" | "audit"

function Card({ title, sub, action, children, label }: { title: string; sub?: ReactNode; action?: ReactNode; children: ReactNode; label?: string }) {
  return (
    <section className="cn-card" aria-label={label ?? title}>
      <div className="cn-cardhead">
        <div style={{ flex: "1 1 200px", minWidth: 0 }}>
          <h2 className="cn-h2" style={{ margin: 0, fontSize: 15 }}>
            {title}
          </h2>
          {sub ? <div className="cn-sub" style={{ fontSize: 13, marginTop: 2 }}>{sub}</div> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function ReadyStep({ n, state, title, sub }: { n: number; state: "ok" | "bad" | "wait"; title: string; sub: string }) {
  return (
    <div className={`cn-step${state === "ok" ? "" : ` ${state}`}`}>
      <span className={`cn-check ${state}`} aria-hidden>
        {state === "ok" ? <Check size={13} strokeWidth={3} /> : state === "bad" ? "!" : n}
      </span>
      <span className="t">{title}</span>
      <span className="s">{sub}</span>
    </div>
  )
}

function ActionsTable({ actions, usedBy }: { actions: ConnectorActionDefinition[]; usedBy: (a: ConnectorActionDefinition) => Workflow[] }) {
  if (actions.length === 0) {
    return (
      <p className="cn-sub" style={{ margin: 0, padding: "16px 20px" }}>
        The capability catalog lists no live actions for this system yet.
      </p>
    )
  }
  return (
    <div className="cn-tblwrap" role="table" aria-label="Actions">
      <div className="cn-atr head" role="row">
        <span className="cn-td cn-th" role="columnheader">Action</span>
        <span className="cn-td cn-th" role="columnheader">Kind</span>
        <span className="cn-td cn-th" role="columnheader">Authority</span>
        <span className="cn-td cn-th" role="columnheader">Used by</span>
      </div>
      {actions.map((action) => {
        const auth = authorityOf(action)
        const users = usedBy(action)
        return (
          <div className="cn-atr" role="row" key={action.tool}>
            <span className="cn-td" role="cell" style={{ minWidth: 0 }}>
              <span className="cn-ellip" style={{ display: "block", fontWeight: 500 }}>{action.name}</span>
              <span className="key cn-ellip">{action.tool}</span>
            </span>
            <span className="cn-td" role="cell">
              <span className={`cn-tag ${action.kind === "read" ? "read" : "write"}`}>{action.kind === "read" ? "Read" : "Write"}</span>
            </span>
            <span className="cn-td" role="cell">
              <span className={`cn-tag ${auth.cls}`}>{auth.label}</span>
            </span>
            <span className="cn-td cn-ellip" role="cell" style={{ fontSize: 13, color: users.length ? "var(--gv-text-2)" : "var(--gv-muted)" }}>
              {users.length ? users.map((w) => w.name).join(", ") : "—"}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function UsageList({
  connector,
  agents,
  workflows,
  plays,
  paused,
}: {
  connector: DetailConnector
  agents: ConnectorAgentRef[]
  workflows: Workflow[]
  plays: PlayRef[]
  paused: boolean
}) {
  if (agents.length + workflows.length + plays.length === 0) {
    return (
      <p className="cn-sub" style={{ margin: 0, padding: "16px 20px" }}>
        No agents, workflows or plays use {connector.type} yet. Give an agent access to {connector.type} from its settings, or add it to a workflow step.
      </p>
    )
  }
  const pill = paused ? <StatusPill status="offline" label="Paused" /> : <StatusPill status="connected" label="Active" />
  return (
    <div>
      {agents.map((agent) => (
        <Link key={`a${agent.id}`} href={`/agents/${agent.id}`} className="cn-uitem">
          <span className="cn-ico blue" aria-hidden>
            <Bot size={18} />
          </span>
          <span className="body">
            <span className="t cn-ellip" style={{ display: "block" }}>{agent.name}</span>
            <span className="s cn-ellip" style={{ display: "block" }}>{["Agent", agent.department, agent.role].filter(Boolean).join(" · ")}</span>
          </span>
          {pill}
        </Link>
      ))}
      {workflows.map((w) => (
        <Link key={`w${w.id}`} href={`/workflows/${w.id}`} className="cn-uitem">
          <span className="cn-ico mute" aria-hidden>
            <WorkflowIcon size={18} />
          </span>
          <span className="body">
            <span className="t cn-ellip" style={{ display: "block" }}>{w.name}</span>
            <span className="s cn-ellip" style={{ display: "block" }}>{["Workflow", w.description].filter(Boolean).join(" · ")}</span>
          </span>
          {pill}
        </Link>
      ))}
      {plays.map((p) => (
        <Link key={`p${p.key}`} href={`/plays/${p.key}`} className="cn-uitem">
          <span className="cn-ico warn" aria-hidden>
            <Zap size={18} />
          </span>
          <span className="body">
            <span className="t cn-ellip" style={{ display: "block" }}>{p.name}</span>
            <span className="s cn-ellip" style={{ display: "block" }}>
              Play · {p.ready ? "ready to run" : p.waiting ? "waiting on a connector" : "needs setup"}
            </span>
          </span>
          {paused || !p.ready ? <StatusPill status="offline" label={paused ? "Paused" : "Not ready"} /> : <StatusPill status="connected" label="Ready" />}
        </Link>
      ))}
    </div>
  )
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      className="cn-iconbtn"
      aria-label={`Copy ${label}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1600)
        } catch {
          toast.error(`Could not copy the ${label}`, { topic: "Clipboard" })
        }
      }}
    >
      {copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
    </button>
  )
}

/* ------------------------------------------------------------------ Page */

export default function ConnectorDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { user } = useAuth()
  const connectorId = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : ""
  const key = user && connectorId ? `/api/connectors/${connectorId}` : null
  const { data, error, isLoading, mutate } = useSWR<unknown>(key, apiFetcher, { revalidateOnFocus: false })
  const connector = useMemo(() => (data ? normalizeDetail(data) : null), [data])
  const enabled = Boolean(user && connector)

  const activityKey = enabled ? `/api/connectors/${connectorId}/activity?limit=200` : null
  const { data: activity, mutate: mutateActivity } = useSWR<{ events: ActivityEvent[]; total: number }>(activityKey, apiFetcher, {
    revalidateOnFocus: false,
  })
  const { data: snapshot } = useSWR<CapabilitySnapshot>(enabled ? "/api/capabilities" : null, apiFetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
  })
  const capabilities = useVendorCapabilities(enabled)
  const agentsByVendor = useAgentsByVendor(enabled)
  const playUsage = usePlays(enabled)
  const workflowUsage = useWorkflows(enabled)

  usePublishGravitreAISelection(connector ? { kind: "connector", id: connector.id, label: connector.name } : null)

  const [tab, setTab] = useState<Tab>("overview")
  const [configureOpen, setConfigureOpen] = useState(false)
  const [removeOpen, setRemoveOpen] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [testing, setTesting] = useState(false)
  const [savingInterval, setSavingInterval] = useState(false)

  if (!user || isLoading || !connector) {
    return (
      <AppShell title="Connector">
        <ConnectorsOverlaysProvider>
          <div className="gv-ws" style={{ minHeight: "100%", background: "var(--gv-canvas)" }}>
            <div className="cn-page" style={{ alignItems: "center", justifyContent: "center", paddingTop: 96 }}>
              {!user || isLoading ? (
                <>
                  <Spinner size="lg" />
                  <p className="cn-sub">Loading connector…</p>
                </>
              ) : (
                <>
                  <Illustration name="moment-error" width={190} />
                  <h2 className="cn-h2" style={{ margin: 0 }}>Connector not found</h2>
                  <p className="cn-sub" style={{ margin: 0 }}>
                    {error instanceof Error ? error.message : "This connector may have been removed."}
                  </p>
                  <Link href="/connectors" className="gv-btn outline sm">
                    Back to connectors
                  </Link>
                </>
              )}
            </div>
          </div>
        </ConnectorsOverlaysProvider>
      </AppShell>
    )
  }

  const vendor = connector.vendorKey || connector.type
  const attention = deriveConnectorAttention(connector)
  const status = hubStatusOf(connector, attention !== null)
  const a = connector.availability
  const capability = capabilities.get(vendor)
  const liveActions = capability?.actions ?? []
  const allActions = (snapshot?.actions ?? []).filter((x) => connectorVendorKey(x.vendor) === vendor)
  const totalActions = Math.max(allActions.length, liveActions.length)
  const agents = agentsByVendor.get(vendor) ?? []
  const workflows = workflowUsage.forVendor(vendor)
  const plays = playUsage.byVendor.get(vendor) ?? []
  const usageCount = agents.length + workflows.length + plays.length
  const usage = usageSentence(agents.length, workflows.length, plays.length)
  const expired = attention?.kind === "expired"
  const paused = a ? !a.executable : connector.status !== "connected" && connector.status !== "syncing"
  const isOAuth = connector.authType === "oauth"
  const cover = coverFor(vendor, connector.category)
  const dept = CONNECTOR_DEPARTMENTS.find((d) => d.categories.includes(connector.category ?? ""))?.label
  const events = activity?.events ?? []
  const scopes = connector.credentials?.grantedScopes ?? []
  const tokenExpiresAt = connector.credentials?.tokenExpiresAt ?? null
  const usedByAction = (action: ConnectorActionDefinition) =>
    workflows.filter((w) => {
      try {
        return JSON.stringify([w.active_version?.definition, ...(w.versions ?? []).map((v) => v.definition)]).includes(`"${action.tool}"`)
      } catch {
        return false
      }
    })

  const dialogConnector: DialogConnector = {
    id: connector.id,
    name: connector.name,
    type: connector.type,
    vendorKey: vendor,
    environment: connector.environment,
    authType: connector.authType,
    authStatus: connector.authStatus,
    maskedApiKey: connector.maskedApiKey,
    authProvider: connector.authProvider,
    syncFrequency: connector.syncFrequency,
    blockingReason: connector.blockingReason ?? null,
    recordsSynced: connector.recordsSynced,
  }

  const refresh = async () => {
    await Promise.all([mutate(), mutateActivity()])
  }

  const handleReconnect = () =>
    reconnectConnector(
      { id: connector.id, name: connector.name, type: connector.type, vendorKey: vendor, authStatus: connector.authStatus, config: connector.config },
      refresh,
    )

  const handleSync = async () => {
    setSyncing(true)
    try {
      await connectorsApi.sync(connector.id)
      toast.success(`${connector.type} sync started`, { vendor, topic: "Sync", description: "New records show up here as the sync finishes." })
      await refresh()
    } catch (err) {
      toast.error(`Could not sync ${connector.type}`, { vendor, topic: "Sync", description: formatUnknownError(err) })
    } finally {
      setSyncing(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    try {
      const result = await connectorsApi.testConnection(connector.id)
      if (result.success) toast.success(`${connector.type} answered`, { vendor, topic: "Live check", description: result.message })
      else toast.warning(`${connector.type} did not pass the check`, { vendor, topic: "Live check", description: result.message })
      await refresh()
    } catch (err) {
      toast.error("Live check failed", { vendor, topic: "Live check", description: formatUnknownError(err) })
    } finally {
      setTesting(false)
    }
  }

  const handleConfigure = async (patch: ConfigurePatch): Promise<boolean> => {
    try {
      await connectorsApi.update(connector.id, patch as Record<string, unknown>)
      toast.success(`${connector.name} settings saved`, {
        vendor,
        topic: "Configuration",
        description: patch.apiKey ? "The new key is stored encrypted. Run a test to confirm it works." : undefined,
        action: patch.apiKey ? { label: "Test now", onClick: () => void handleTest() } : undefined,
      })
      await refresh()
      return true
    } catch (err) {
      toast.error(`Could not save ${connector.name}`, { vendor, topic: "Configuration", description: formatUnknownError(err) })
      return false
    }
  }

  const handleInterval = async (value: string) => {
    setSavingInterval(true)
    try {
      await connectorsApi.update(connector.id, { syncFrequency: value } as Record<string, unknown>)
      toast.success(`Sync set to ${syncIntervalLabel(value).toLowerCase()}`, { vendor, topic: "Sync" })
      await refresh()
    } catch (err) {
      toast.error("Could not change the sync interval", { vendor, topic: "Sync", description: formatUnknownError(err) })
    } finally {
      setSavingInterval(false)
    }
  }

  const handleRemove = async (confirmName: string): Promise<boolean> => {
    try {
      await connectorsApi.delete(connector.id, confirmName)
      toast.success(`${connector.name} removed`, {
        vendor,
        topic: "Removed",
        description: "Agents and workflows no longer use it. The removal receipt is on the Connectors page.",
      })
      void globalMutate(DATA_REMOVAL_KEY)
      void globalMutate("/api/connectors")
      router.push("/connectors")
      return true
    } catch (err) {
      toast.error(`Could not remove ${connector.name}`, { vendor, topic: "Remove", description: formatUnknownError(err) })
      return false
    }
  }

  const exportAudit = () => {
    if (events.length === 0) {
      toast.info("No audit events to export yet", { vendor, topic: "Audit trail" })
      return
    }
    downloadAuditCsv(connector, events)
  }

  /* Readiness: the same four checks the availability service reports. */
  const steps: Array<{ state: "ok" | "bad" | "wait"; title: string; sub: string }> = a
    ? (() => {
        const authorized = a.authenticated && a.tokenValid
        const list: Array<{ state: "ok" | "bad" | "wait"; title: string; sub: string }> = [
          { state: a.configured ? "ok" : "bad", title: "Connected", sub: a.configured ? `Linked ${formatDate(connector.createdAt) || ""}`.trim() : "Setup needed" },
          {
            state: authorized ? "ok" : "bad",
            title: "Authorized",
            sub: !a.authenticated ? "Not signed in" : a.tokenValid ? "Valid" : `Token expired${isOAuth ? " · reconnect" : " · replace the key"}`,
          },
          {
            state: a.scopesValid ? "ok" : authorized ? "bad" : "wait",
            title: "Permissions granted",
            sub: a.scopesValid ? (scopes.length ? `${scopes.length} scopes` : "Granted") : "A required scope is missing",
          },
        ]
        const firstBad = list.findIndex((s) => s.state === "bad")
        list.push({
          state: a.executable ? "ok" : "wait",
          title: "Agents can act",
          sub: a.executable ? "Yes" : firstBad >= 0 ? `Resumes after step ${firstBad + 1}` : "Paused",
        })
        return list
      })()
    : []
  const doneSteps = steps.filter((s) => s.state === "ok").length

  const statusTile = (() => {
    const cls = status === "attention" ? "bad" : status === "connected" ? "good" : status === "syncing" ? "blue" : ""
    const label = status === "attention" ? (expired ? "Reconnect needed" : attention?.actionLabel ?? "Needs attention") : status === "connected" ? "Connected" : status === "syncing" ? "Syncing" : "Offline"
    const sub = expired && tokenExpiresAt ? `Since ${formatDate(tokenExpiresAt)}` : a?.lastCheckedAt ? `Checked ${relativeTime(a.lastCheckedAt).toLowerCase()}` : "Not checked yet"
    return { cls, label, sub }
  })()

  const primaryFix = attention
    ? attention.action === "reconnect"
      ? { label: `Reconnect ${connector.type}`, run: () => void handleReconnect() }
      : attention.action === "configure"
        ? { label: attention.actionLabel, run: () => setConfigureOpen(true) }
        : { label: "Run a live check", run: () => void handleTest() }
    : null

  const tabs: Array<{ id: Tab; label: string; n?: number }> = [
    { id: "overview", label: "Overview" },
    { id: "actions", label: "Actions", n: liveActions.length },
    { id: "used", label: "Used by", n: usageCount },
    { id: "credentials", label: "Credentials" },
    { id: "audit", label: "Audit trail", n: activity?.total ?? events.length },
  ]

  const authMethod = isOAuth
    ? `OAuth 2.0 · ${connector.authProvider === "managed" ? "managed" : "direct"}`
    : connector.authType === "webhook"
      ? "Webhook"
      : "API key"

  const tokenRow = isOAuth ? (
    <div className="cn-code">
      <span>
        {connector.credentials?.hasOAuthTokens
          ? expired
            ? `Stored · expired${tokenExpiresAt ? ` ${formatDate(tokenExpiresAt)}` : ""}`
            : tokenExpiresAt
              ? `Stored · refreshes ${formatDateTime(tokenExpiresAt)}`
              : "Stored"
          : "Not authorized yet"}
      </span>
      {expired ? <StatusPill status="attention" label="Expired" /> : connector.credentials?.hasOAuthTokens ? <StatusPill status="connected" label="Valid" /> : null}
    </div>
  ) : (
    <div className="cn-code">
      <span>{connector.maskedApiKey ? `Stored · ${connector.maskedApiKey}` : "Not set"}</span>
      {expired ? <StatusPill status="attention" label="Rejected" /> : null}
    </div>
  )

  const credentialsCard = (full: boolean) => (
    <section className="cn-card cn-pad" aria-label="Credentials" data-testid="connector-detail-config">
      <div className="cn-row-flex" style={{ gap: 10, fontWeight: 600 }}>
        <span className="cn-ico sm warn" aria-hidden>
          <KeyRound size={15} />
        </span>
        Credentials
      </div>
      <p className="cn-sub" style={{ margin: 0, fontSize: 13 }}>
        Secrets are write only. Gravitre encrypts them and never shows them again, not even to admins.
      </p>
      <div className="cn-field">
        Auth method
        <div className="cn-code">
          <span>{authMethod}</span>
        </div>
      </div>
      <div className="cn-field">
        {isOAuth ? "Access token" : "API key"}
        {tokenRow}
      </div>
      {isOAuth ? (
        <div className="cn-field">
          Granted scopes
          {scopes.length ? (
            <div className="cn-scopes">
              {(full ? scopes : scopes.slice(0, 4)).map((s) => (
                <span key={s} className="cn-scope">
                  {s}
                </span>
              ))}
              {!full && scopes.length > 4 ? (
                <button type="button" className="cn-scope" onClick={() => setTab("credentials")}>
                  +{scopes.length - 4} more
                </button>
              ) : null}
            </div>
          ) : (
            <span style={{ color: "var(--gv-muted)" }}>{connector.credentials?.hasOAuthTokens ? "The provider did not report scopes." : "Shown after sign-in."}</span>
          )}
        </div>
      ) : null}
      <div className="cn-row-flex" style={{ gap: 8 }}>
        {isOAuth ? (
          <button type="button" className="gv-btn outline sm" onClick={() => void handleReconnect()}>
            Reconnect with OAuth
          </button>
        ) : (
          <button type="button" className="gv-btn outline sm" onClick={() => setConfigureOpen(true)}>
            Replace key
          </button>
        )}
        {!full && isOAuth && scopes.length ? (
          <button type="button" className="cn-btn-text sm" onClick={() => setTab("credentials")}>
            Review scopes
          </button>
        ) : null}
      </div>
    </section>
  )

  const syncCard = (
    <section className="cn-card cn-pad" aria-label="Sync" data-testid="connector-detail-status">
      <div className="cn-row-flex" style={{ gap: 10, fontWeight: 600 }}>
        <span className="cn-ico sm blue" aria-hidden>
          <RefreshCw size={15} />
        </span>
        Sync
      </div>
      <label className="cn-field">
        Sync interval
        <select
          className="cn-select full"
          value={SYNC_INTERVALS.some((o) => o.value === connector.syncFrequency) ? connector.syncFrequency ?? "1h" : "1h"}
          disabled={savingInterval}
          onChange={(e) => void handleInterval(e.target.value)}
        >
          {SYNC_INTERVALS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      {connector.webhookUrl ? (
        <div className="cn-field">
          Webhook URL
          <div className="cn-code">
            <span>{connector.webhookUrl}</span>
            <CopyButton text={connector.webhookUrl} label="webhook URL" />
          </div>
        </div>
      ) : null}
      <KnowledgeSyncRow connectorId={connector.id} vendor={vendor} status={connector.rawStatus} />
    </section>
  )

  const removeCard = (
    <section className="cn-card cn-pad" aria-label="Remove connector">
      <div style={{ fontWeight: 600 }}>Remove connector</div>
      <p className="cn-sub" style={{ margin: 0, fontSize: 13 }}>
        Stops every agent and workflow that uses {connector.type} and removes synced data on your retention schedule. Your {connector.type} account is not changed.
      </p>
      <button type="button" className="gv-btn danger sm" style={{ alignSelf: "flex-start" }} onClick={() => setRemoveOpen(true)}>
        <Trash2 size={14} aria-hidden /> Remove {connector.type}
      </button>
    </section>
  )

  const readinessCard = (
    <Card
      title="Ready to act"
      sub={
        steps.length
          ? doneSteps === steps.length
            ? "All 4 steps done · agents can act now"
            : `${doneSteps} of ${steps.length} steps done${steps.filter((s) => s.state === "bad").length === 1 ? " · one fix away from live" : ""}`
          : "Run a live check to see each step"
      }
      action={
        steps.length ? null : (
          <button type="button" className="gv-btn outline sm" disabled={testing} onClick={() => void handleTest()}>
            {testing ? <Loader2 size={14} className="cno-spin" aria-hidden /> : null} Run live check
          </button>
        )
      }
    >
      {steps.length ? (
        <div className="cn-steps">
          {steps.map((s, i) => (
            <ReadyStep key={s.title} n={i + 1} {...s} />
          ))}
        </div>
      ) : null}
    </Card>
  )

  const actionsCard = (full: boolean) => (
    <Card
      title={`What agents can do in ${connector.type}`}
      label="Actions"
      sub="The lowest authority each action needs. Same levels as Plays: Observe reads, Recommend asks you first, Act runs inside guardrails."
      action={
        !full && liveActions.length > 6 ? (
          <button type="button" className="cn-btn-text sm" onClick={() => setTab("actions")}>
            All {liveActions.length} actions <ArrowRight size={14} aria-hidden />
          </button>
        ) : null
      }
    >
      <div data-testid="connector-detail-linkage">
        <ActionsTable actions={full ? liveActions : liveActions.slice(0, 6)} usedBy={usedByAction} />
      </div>
    </Card>
  )

  const usageCard = (
    <Card
      title={`Agents, workflows and plays using ${connector.type}`}
      sub={usageCount ? (paused ? `All paused until ${connector.type} ${expired ? "is reconnected" : "can act again"}` : `${usage} rely on it`) : undefined}
    >
      <UsageList connector={connector} agents={agents} workflows={workflows} plays={plays} paused={paused} />
    </Card>
  )

  const auditCard = (
    <Card
      title="Audit trail"
      sub={activity ? `${activity.total} ${activity.total === 1 ? "event" : "events"} recorded for this connector` : "Loading events…"}
      action={
        <button type="button" className="gv-btn outline sm" onClick={exportAudit}>
          <Download size={14} aria-hidden /> Export CSV
        </button>
      }
    >
      {events.length ? (
        <ul className="cn-audit">
          {events.map((e) => (
            <li key={e.id}>
              <time dateTime={e.createdAt ?? undefined}>{formatDateTime(e.createdAt)}</time>
              <span>
                {auditLabel(e.action)}
                <span className="cn-sub" style={{ fontSize: 12, marginLeft: 8, fontFamily: "var(--font-mono), monospace" }}>
                  {e.action}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="cn-sub" style={{ margin: 0, padding: "16px 20px" }}>
          {activity ? "No events yet. Syncs, sign-ins and setting changes show up here." : "Loading…"}
        </p>
      )}
    </Card>
  )

  return (
    <AppShell title={connector.name} breadcrumbVendor={connector.type}>
      <ConnectorsOverlaysProvider>
        <div className="gv-ws" data-composition="manage" style={{ minHeight: "100%", background: "var(--gv-canvas)" }}>
          <div className="cn-page" data-testid="connector-detail-b">
            <div className="cn-crumbs">
              <nav aria-label="Breadcrumb" className="cn-eyebrow">
                <Link href="/connectors" style={{ color: "inherit", textDecoration: "none" }}>
                  Integrate / Connectors
                </Link>{" "}
                / {connector.name}
              </nav>
              <button type="button" className={`cn-live${a?.lastCheckedAt ? "" : " stale"}`} onClick={() => void handleTest()} disabled={testing}>
                <span className="d" aria-hidden />
                {testing ? "Checking…" : a?.lastCheckedAt ? `Checked ${relativeTime(a.lastCheckedAt).toLowerCase()}` : "Not checked yet"}
              </button>
            </div>

            <section className="cn-card" style={{ overflow: "hidden" }}>
              <div className="cn-cover">
                <ConnectorCover vendor={vendor} category={connector.category} />
                <span className="cn-cover-chips">
                  <span>Connector</span>
                  <span className="dark">{[dept, cover.label].filter(Boolean).join(" · ")}</span>
                </span>
              </div>
              <div className="cn-idrow">
                <VendorTile vendor={vendor} category={connector.category} size="lg" />
                <div className="cn-idname">
                  <div className="cn-row-flex" style={{ gap: 10 }}>
                    <h1 className="cn-h1" style={{ margin: 0 }}>
                      {connector.name}
                    </h1>
                    <StatusPill status={status} label={status === "attention" ? statusTile.label : undefined} />
                    <span className={`cn-pill ${connector.environment === "production" ? "connected" : "amber"}`}>
                      {connector.environment === "production" ? "Production" : "Staging"}
                    </span>
                  </div>
                  <p className="cn-sub" style={{ margin: "6px 0 0" }}>
                    {[connector.description, authMethod, connector.createdAt ? `added ${formatDate(connector.createdAt)}` : ""].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <div className="cn-row-flex" style={{ gap: 8 }}>
                  {isOAuth && (expired || attention?.action === "reconnect") ? (
                    <button type="button" className="gv-btn green sm" onClick={() => void handleReconnect()}>
                      Reconnect
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="gv-btn outline sm"
                    disabled={syncing || expired || connector.status === "disconnected"}
                    title={expired ? "Reconnect first" : undefined}
                    onClick={() => void handleSync()}
                  >
                    {syncing ? <Loader2 size={14} className="cno-spin" aria-hidden /> : null}
                    {syncing ? "Syncing…" : "Sync now"}
                  </button>
                  <button type="button" className="gv-btn outline sm" onClick={() => setConfigureOpen(true)}>
                    Configure
                  </button>
                  <AskGravitreSummonButton
                    className="gv-btn outline sm"
                    selected={{ kind: "connector", id: connector.id, label: connector.name }}
                    prompt={attention ? `Why is ${connector.name} not working, and how do I fix it?` : `What can agents do with ${connector.name}?`}
                  />
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button type="button" className="gv-btn outline sm" aria-label="More connector actions" style={{ padding: "0 10px" }}>
                        <MoreHorizontal size={16} aria-hidden />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => void handleTest()}>
                        <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Run live check
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={exportAudit}>
                        <Download className="mr-2 h-4 w-4" aria-hidden /> Export audit log
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="text-destructive" onSelect={() => setRemoveOpen(true)}>
                        <Trash2 className="mr-2 h-4 w-4" aria-hidden /> Remove connector
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </section>

            {attention ? (
              <div role="alert" className="cn-card cn-row-flex" style={{ gap: 14, padding: "14px 16px", borderColor: "#f0cdd1" }}>
                <span className="cn-ico bad" aria-hidden>
                  <AlertTriangle size={18} />
                </span>
                <div style={{ flex: "1 1 320px", minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>
                    {expired && tokenExpiresAt ? `Authorization expired on ${formatDateTime(tokenExpiresAt)}` : attention.problem}
                  </div>
                  <div className="cn-sub" style={{ marginTop: 2, lineHeight: 1.5 }}>
                    {attention.evidence}
                    {usage ? ` ${usage} ${usageCount === 1 ? "is" : "are"} paused. Nothing was lost; they resume once it is fixed.` : ""}
                  </div>
                </div>
                {primaryFix ? (
                  <button type="button" className="gv-btn dark sm" onClick={primaryFix.run}>
                    {primaryFix.label}
                  </button>
                ) : null}
              </div>
            ) : null}

            <div className="cn-tiles">
              <div className={`cn-tile ${statusTile.cls}`}>
                <span className="l">Status</span>
                <span className="v" style={{ fontSize: 20 }}>{statusTile.label}</span>
                <span className="s">{statusTile.sub}</span>
              </div>
              <div className="cn-tile">
                <span className="l">Last successful sync</span>
                <span className="v" style={{ fontSize: 20 }}>{formatDateTime(connector.lastSyncAt)}</span>
                <span className="s">{connector.recordsSynced ? `${connector.recordsSynced.toLocaleString()} records` : "No records synced yet"}</span>
              </div>
              <div className="cn-tile">
                <span className="l">Sync interval</span>
                <span className="v" style={{ fontSize: 20 }}>{syncIntervalLabel(connector.syncFrequency)}</span>
                <span className="s">{paused ? "Paused while access is blocked" : "Running on schedule"}</span>
              </div>
              <button type="button" className="cn-tile" onClick={() => setTab("actions")}>
                <span className="l">Actions available</span>
                <span className="v" style={{ fontSize: 20 }}>{totalActions ? `${liveActions.length} of ${totalActions}` : "—"}</span>
                <span className="s">{capability ? `${capability.read} read · ${capability.write} write` : "Not in the capability catalog"}</span>
              </button>
            </div>

            <div className="cn-tabs" role="tablist" aria-label="Connector sections">
              {tabs.map((t) => (
                <button key={t.id} type="button" role="tab" className="cn-tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
                  {t.label}
                  {t.n != null ? <span className="n">{t.n}</span> : null}
                </button>
              ))}
            </div>

            <div className="cn-cols">
              <div className="cn-main" role="tabpanel">
                {tab === "overview" ? (
                  <>
                    {readinessCard}
                    {actionsCard(false)}
                    {usageCard}
                    {vendor === "freshservice" ? <FreshserviceTriggersPanel connectorId={connector.id} /> : null}
                  </>
                ) : null}
                {tab === "actions" ? actionsCard(true) : null}
                {tab === "used" ? usageCard : null}
                {tab === "credentials" ? credentialsCard(true) : null}
                {tab === "audit" ? auditCard : null}
              </div>
              <aside className="cn-side" aria-label="Configuration">
                {tab === "credentials" ? null : credentialsCard(false)}
                {syncCard}
                {removeCard}
              </aside>
            </div>
          </div>
        </div>

        <ConfigureConnectorDialog
          connector={dialogConnector}
          open={configureOpen}
          onOpenChange={setConfigureOpen}
          onSave={handleConfigure}
          onReconnect={
            isOAuth
              ? () => {
                  setConfigureOpen(false)
                  void handleReconnect()
                }
              : undefined
          }
          missingScopeNote={attention?.kind === "scope" ? (agents[0] ? `needed by ${agents[0].name}` : attention.evidence) : null}
        />
        <RemoveConnectorDialog
          connector={dialogConnector}
          open={removeOpen}
          onOpenChange={setRemoveOpen}
          onRemove={handleRemove}
          agents={agents.length}
          workflows={workflows.length}
          plays={plays.length}
        />
      </ConnectorsOverlaysProvider>
    </AppShell>
  )
}

const KNOWLEDGE_VENDORS = new Set(["notion", "confluence", "hubspot", "zendesk"])

/** Sync to Knowledge: runs the real knowledge sync for systems the knowledge pipeline reads. */
function KnowledgeSyncRow({ connectorId, vendor, status }: { connectorId: string; vendor: string; status: string }) {
  if (!KNOWLEDGE_VENDORS.has(vendor)) return null
  return (
    <div className="cn-mini">
      <div style={{ flex: "1 1 auto", minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>Sync to Knowledge</div>
        <div style={{ fontSize: 12, color: "var(--gv-muted)" }}>
          {["active", "healthy", "connected"].includes(status.toLowerCase())
            ? "Agents can cite what this system holds. Runs on the interval above."
            : "Paused until the connection works again."}
        </div>
      </div>
      <KnowledgeSyncButton connectorId={connectorId} connectorType={vendor} connectorStatus={status} className="gv-btn outline sm" />
    </div>
  )
}
