"use client"

import Link from "next/link"
import { useMemo, type ReactNode } from "react"
import useSWR from "swr"
import { ArrowRight, Bot, ExternalLink, RefreshCw, Settings, ShieldCheck, Wifi } from "lucide-react"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import {
  ContextFacts,
  GravitreContextCard,
  GravitreTaskList,
  GravitreTaskRow,
  ReadinessCheck,
} from "@/components/gravitre/ai-native"
import { Button } from "@/components/ui/button"
import { connectorVendorKey } from "@/lib/connectors"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { allActions, type ConnectorActionCatalogResponse, type ConnectorActionDefinition } from "@/lib/connector-actions"
import { cn } from "@/lib/utils"

/** Structural subset of the Connectors page model; only fields the backend really sends. */
export interface OperatingConnector {
  id: string
  name: string
  type: string
  vendorKey: string
  status: "connected" | "disconnected" | "error" | "syncing"
  environment: "production" | "staging"
  lastSync: string
  category?: string
  authType?: "oauth" | "apiKey" | "webhook"
  authStatus?: string
  blockingReason?: string
  recoveryAction?: string
  availability?: {
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
  }
  config?: { instance_url?: string; subdomain?: string; owner?: string; repo?: string }
}

export type VendorCapability = {
  read: number
  write: number
  advanced: number
  approval: number
  actions: ConnectorActionDefinition[]
}

/** Per-vendor action catalog (GET /api/connectors/catalog/actions): static product data, not usage. */
export function useVendorCapabilities(enabled: boolean): Map<string, VendorCapability> {
  const { data } = useSWR<ConnectorActionCatalogResponse>(
    enabled ? "/api/connectors/catalog/actions" : null,
    apiFetcher,
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
  )
  return useMemo(() => {
    const map = new Map<string, VendorCapability>()
    for (const vendor of data?.vendors ?? []) {
      const actions = allActions(vendor).filter((a) => a.implemented)
      map.set(connectorVendorKey(vendor.vendor), {
        read: actions.filter((a) => a.kind === "read").length,
        write: actions.filter((a) => a.kind === "write").length,
        advanced: actions.filter((a) => a.kind === "advanced").length,
        approval: actions.filter((a) => a.requiresApproval).length,
        actions,
      })
    }
    return map
  }, [data])
}

export type ConnectorAgentRef = { id: string; name: string; role?: string; department?: string; avatarColor?: string }

type AgentLike = {
  id?: string
  name?: string
  role?: string
  department?: string
  avatarColor?: string
  permissions?: unknown
  connectedSystems?: unknown
}

/** Agents whose configured systems include the vendor (agents.systems / connectedSystems). */
export function useAgentsByVendor(enabled: boolean): Map<string, ConnectorAgentRef[]> {
  const { data } = useSWR<{ agents?: AgentLike[] }>(enabled ? "/api/agents" : null, apiFetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  })
  return useMemo(() => {
    const map = new Map<string, ConnectorAgentRef[]>()
    for (const agent of data?.agents ?? []) {
      if (!agent?.id || !agent.name) continue
      const systems = [
        ...(Array.isArray(agent.permissions) ? agent.permissions : []),
        ...(Array.isArray(agent.connectedSystems) ? agent.connectedSystems : []),
      ]
      const keys = new Set(systems.map((s) => connectorVendorKey(String(s))).filter(Boolean))
      for (const key of keys) {
        const list = map.get(key) ?? []
        list.push({ id: agent.id, name: agent.name, role: agent.role, department: agent.department, avatarColor: agent.avatarColor })
        map.set(key, list)
      }
    }
    return map
  }, [data])
}

const BLOCKING_COPY: Record<string, string> = {
  token_expired: "Authorization expired or was revoked at the provider.",
  missing_scope: "The connected account is missing a required permission scope.",
  pending_auth: "Authorization was started but never completed.",
  misconfigured: "Connection settings are incomplete.",
  unsupported_action: "The requested action is not supported by this connection.",
}

export function describeBlocking(reason?: string): string | undefined {
  if (!reason) return undefined
  return BLOCKING_COPY[reason] ?? reason
}

export type ConnectorAttention = {
  connector: OperatingConnector
  problem: string
  evidence: string
  action: "reconnect" | "configure" | "test"
  actionLabel: string
}

/** Attention items derived only from reported state; returns nothing for healthy connectors. */
export function deriveConnectorAttention(connector: OperatingConnector): ConnectorAttention | null {
  const a = connector.availability
  const reason = a?.blockingReason ?? connector.blockingReason
  const expired = reason === "token_expired" || connector.authStatus === "auth_expired" || (a ? a.authenticated && !a.tokenValid : false)
  const evidence =
    describeBlocking(reason) ??
    (a?.recoveryAction || connector.recoveryAction) ??
    (connector.status === "error" ? "The last availability check reported an error." : "")
  if (expired) {
    return {
      connector,
      problem: `${connector.name} access expired`,
      evidence: evidence || "The stored token is no longer valid.",
      action: connector.authType === "oauth" ? "reconnect" : "configure",
      actionLabel: connector.authType === "oauth" ? "Reconnect" : "Update credentials",
    }
  }
  if (reason === "missing_scope" || (a && a.authenticated && !a.scopesValid)) {
    return {
      connector,
      problem: `${connector.name} permission missing`,
      evidence: evidence || "A required scope was not granted.",
      action: connector.authType === "oauth" ? "reconnect" : "configure",
      actionLabel: "Grant scope",
    }
  }
  if (reason === "pending_auth" || connector.authStatus === "pending_auth" || (a && a.configured && !a.authenticated)) {
    return {
      connector,
      problem: `${connector.name} is not authorized`,
      evidence: evidence || "Authorization has not been completed.",
      action: connector.authType === "oauth" ? "reconnect" : "configure",
      actionLabel: "Authorize",
    }
  }
  if (reason || connector.status === "error" || (a && !a.healthy)) {
    return {
      connector,
      problem: `${connector.name} cannot act`,
      evidence: evidence || "The last health check failed.",
      action: "test",
      actionLabel: "Inspect failure",
    }
  }
  return null
}

const DOT: Record<OperatingConnector["status"], string> = {
  connected: "bg-[color:var(--g-brand)]",
  syncing: "bg-[color:var(--status-running)]",
  error: "bg-destructive",
  disconnected: "bg-muted-foreground/60",
}

function stateDot(connector: OperatingConnector, attention: boolean) {
  return attention && connector.status !== "error" ? "bg-warning" : DOT[connector.status]
}

function capabilitySummary(cap?: VendorCapability): ReactNode {
  if (!cap) return <span className="text-muted-foreground">—</span>
  return (
    <span className="tabular-nums">
      {cap.read} read · {cap.write} write
      {cap.approval > 0 ? <span className="text-muted-foreground"> · {cap.approval} approval</span> : null}
    </span>
  )
}

function AgentStack({ agents }: { agents?: ConnectorAgentRef[] }) {
  if (!agents?.length) return <span className="text-muted-foreground">—</span>
  const shown = agents.slice(0, 3)
  return (
    <span className="flex items-center gap-1.5" title={agents.map((a) => a.name).join(", ")}>
      <span className="flex -space-x-1">
        {shown.map((agent) => (
          <AgentIdentityAvatar key={agent.id} agent={agent} size="xs" showStatusDot={false} className="ring-2 ring-[color:var(--g-canvas)]" />
        ))}
      </span>
      <span className="tabular-nums text-foreground">{agents.length}</span>
      <span className="sr-only">agents: {agents.map((a) => a.name).join(", ")}</span>
    </span>
  )
}

export const CONNECTOR_ROW_GRID =
  "lg:grid lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1.05fr)_minmax(0,1.1fr)_minmax(0,0.7fr)_minmax(0,0.8fr)_auto] lg:items-center lg:gap-4"

export function ConnectorRowHeader() {
  return (
    <div
      aria-hidden
      className={cn(
        "hidden border-b border-[color:var(--g-border-default)] px-3 pb-2 text-[11px] font-medium text-muted-foreground",
        CONNECTOR_ROW_GRID,
      )}
    >
      <span>System</span>
      <span>State</span>
      <span>Readiness</span>
      <span>Actions available</span>
      <span>Agents</span>
      <span>Last sync</span>
      <span className="w-[4.5rem]" />
    </div>
  )
}

export function ConnectorOperatingRow({
  connector,
  statusLabel,
  capability,
  agents,
  selected,
  attention,
  onSelect,
  menu,
}: {
  connector: OperatingConnector
  statusLabel: string
  capability?: VendorCapability
  agents?: ConnectorAgentRef[]
  selected: boolean
  attention: boolean
  onSelect: () => void
  menu?: ReactNode
}) {
  const a = connector.availability
  return (
    <div
      data-gravitre-connector-row=""
      data-selected={selected ? "" : undefined}
      className={cn(
        "relative border-b border-[color:var(--g-border-subtle)] px-3 py-2.5 transition-colors",
        CONNECTOR_ROW_GRID,
        selected
          ? "bg-[color:var(--g-surface-active)] before:absolute before:inset-y-0 before:left-0 before:w-[2px] before:bg-[color:var(--signal-500)] dark:bg-[color:var(--graphite-800)]"
          : "hover:bg-[color:var(--g-surface-1)]",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className="flex min-w-0 items-center gap-3 text-left after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-ring"
      >
        <ProviderLogo provider={connector.vendorKey || connector.type} label={connector.type} size="lg" decorative />
        <span className="min-w-0">
          <span className="block truncate text-[13.5px] font-semibold text-foreground">{connector.name}</span>
          <span className="block truncate text-[12px] text-muted-foreground">
            {[connector.type, connector.category, connector.environment === "production" ? "Production" : "Staging"]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </span>
      </button>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] lg:contents">
        <span className="inline-flex min-w-0 items-center gap-1.5">
          <span aria-hidden className={cn("h-2 w-2 shrink-0 rounded-full", stateDot(connector, attention))} />
          <span className={cn("truncate font-medium", attention ? "text-foreground" : "text-foreground/90")}>{statusLabel}</span>
        </span>
        <span className="inline-flex items-center gap-1" aria-label="Readiness">
          {a ? (
            ([
              ["Authorized", a.authenticated && a.tokenValid],
              ["Scopes", a.scopesValid],
              ["Healthy", a.healthy],
              ["Can act", a.executable],
            ] as const).map(([label, ok]) => (
              <span
                key={label}
                title={`${label}: ${ok ? "yes" : "no"}`}
                className={cn(
                  "h-1.5 w-5 rounded-full",
                  ok ? "bg-[color:var(--g-brand)]" : "bg-[color:var(--g-border-strong)]",
                )}
              >
                <span className="sr-only">
                  {label} {ok ? "yes" : "no"}
                </span>
              </span>
            ))
          ) : (
            <span className="text-muted-foreground">Not reported</span>
          )}
          {a ? (
            <span className="ml-1.5 text-muted-foreground">
              {[a.authenticated && a.tokenValid, a.scopesValid, a.healthy, a.executable].filter(Boolean).length}/4
            </span>
          ) : null}
        </span>
        <span className="text-foreground/90">{capabilitySummary(capability)}</span>
        <AgentStack agents={agents} />
        <span className="tabular-nums text-muted-foreground">{connector.lastSync}</span>
        <span className="relative z-[1] ml-auto flex items-center gap-1 lg:ml-0">
          <Link
            href={`/connectors/${connector.id}`}
            className="inline-flex items-center gap-0.5 rounded px-1.5 py-1 text-[12px] font-medium text-foreground hover:bg-[color:var(--g-surface-2)]"
          >
            Details
            <ArrowRight className="h-3 w-3" aria-hidden />
          </Link>
          {menu}
        </span>
      </div>
    </div>
  )
}

export function ConnectorAttentionList({
  items,
  onAction,
}: {
  items: ConnectorAttention[]
  onAction: (item: ConnectorAttention) => void
}) {
  if (items.length === 0) return null
  return (
    <section aria-labelledby="connectors-attention" data-review-surface="connectors-attention" className="mb-5">
      <h2 id="connectors-attention" className="mb-1 flex items-center gap-2 text-[13px] font-semibold text-foreground">
        Needs attention
        <span className="rounded-full bg-warning/15 px-1.5 text-[11.5px] tabular-nums leading-5 text-foreground">{items.length}</span>
      </h2>
      <GravitreTaskList label="Connectors that need attention" className="border-y border-[color:var(--g-border-default)]">
        {items.map((item) => (
          <GravitreTaskRow
            key={item.connector.id}
            state="blocked"
            leading={<ProviderLogo provider={item.connector.vendorKey || item.connector.type} label={item.connector.type} size="md" decorative />}
            title={item.problem}
            detail={item.evidence}
            stateLabel={item.connector.status === "error" ? "Error" : "Blocked"}
            className="px-3"
            action={
              <Button size="sm" variant="outline" className="h-7 gap-1 text-[12px]" onClick={() => onAction(item)}>
                {item.actionLabel}
                <ArrowRight className="h-3 w-3" aria-hidden />
              </Button>
            }
          />
        ))}
      </GravitreTaskList>
    </section>
  )
}

function accountLabel(connector: OperatingConnector): string | null {
  const c = connector.config
  if (!c) return null
  if (c.instance_url) return c.instance_url
  if (c.subdomain) return c.subdomain
  if (c.owner && c.repo) return `${c.owner}/${c.repo}`
  return null
}

function formatChecked(value?: string): string | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString()
}

export function ConnectorInspector({
  connector,
  statusLabel,
  capability,
  agents,
  attention,
  onConfigure,
  onTest,
  onSync,
  onReconnect,
  onClose,
}: {
  connector: OperatingConnector
  statusLabel: string
  capability?: VendorCapability
  agents?: ConnectorAgentRef[]
  attention: ConnectorAttention | null
  onConfigure: () => void
  onTest: () => void
  onSync: () => void
  onReconnect?: () => void
  onClose: () => void
}) {
  const a = connector.availability
  const writes = capability?.actions.filter((x) => x.kind !== "read") ?? []
  const reads = capability?.actions.filter((x) => x.kind === "read") ?? []
  return (
    <aside
      aria-label={`${connector.name} inspector`}
      data-review-surface="connector-inspector"
      className="flex h-fit flex-col gap-3 border-l-0 lg:sticky lg:top-0"
    >
      <GravitreContextCard
        kind="Connector"
        mark={<ProviderLogo provider={connector.vendorKey || connector.type} label={connector.type} size="lg" />}
        title={connector.name}
        subtitle={[connector.type, connector.category].filter(Boolean).join(" · ")}
        status={
          <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-foreground">
            <span aria-hidden className={cn("h-2 w-2 rounded-full", stateDot(connector, Boolean(attention)))} />
            {statusLabel}
          </span>
        }
        footer={
          <div className="flex flex-wrap gap-1.5">
            {onReconnect ? (
              <Button size="sm" className="h-7 gap-1 text-[12px]" onClick={onReconnect}>
                <ExternalLink className="h-3 w-3" aria-hidden />
                Reconnect
              </Button>
            ) : null}
            <Button size="sm" variant="outline" className="h-7 gap-1 text-[12px]" onClick={onConfigure}>
              <Settings className="h-3 w-3" aria-hidden />
              Configure
            </Button>
            <Button size="sm" variant="outline" className="h-7 gap-1 text-[12px]" onClick={onTest}>
              <Wifi className="h-3 w-3" aria-hidden />
              Test
            </Button>
            <Button size="sm" variant="ghost" className="h-7 gap-1 text-[12px]" onClick={onSync}>
              <RefreshCw className="h-3 w-3" aria-hidden />
              Sync
            </Button>
            <Button size="sm" variant="ghost" className="ml-auto h-7 text-[12px]" onClick={onClose}>
              Close
            </Button>
          </div>
        }
      >
        <ContextFacts
          facts={[
            { label: "Provider", value: connector.type },
            { label: "Account", value: accountLabel(connector) },
            { label: "Environment", value: connector.environment === "production" ? "Production" : "Staging" },
            { label: "Auth method", value: connector.authType === "oauth" ? "OAuth" : connector.authType === "webhook" ? "Webhook" : "API key" },
          ]}
        />
      </GravitreContextCard>

      <GravitreContextCard kind="Access" title={a ? (a.executable ? "Agents can act through this system" : "Agents cannot act yet") : "Availability not reported"}>
        {a ? (
          <>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <ReadinessCheck label="Configured" ok={a.configured} />
              <ReadinessCheck label="Authenticated" ok={a.authenticated} />
              <ReadinessCheck label="Token valid" ok={a.tokenValid} />
              <ReadinessCheck label="Scopes granted" ok={a.scopesValid} />
              <ReadinessCheck label="Healthy" ok={a.healthy} />
              <ReadinessCheck label="Can act" ok={a.executable} />
            </div>
            <div className="mt-2 border-t border-[color:var(--g-border-subtle)] pt-2">
              <ContextFacts
                facts={[
                  { label: "Last checked", value: formatChecked(a.lastCheckedAt) },
                  { label: "Source", value: a.sourceOfTruth ?? null },
                ]}
              />
            </div>
          </>
        ) : (
          <p className="text-[12px] text-muted-foreground">Run “Check live status” to evaluate authorization, scopes and health.</p>
        )}
      </GravitreContextCard>

      <GravitreContextCard
        kind="Capabilities"
        title={capability ? `${capability.actions.length} actions in the catalog` : "No catalog entry"}
        subtitle={capability ? `${capability.read} read · ${capability.write} write · ${capability.advanced} advanced` : undefined}
        footer={
          capability ? (
            <Link href={`/connectors/${connector.id}`} className="inline-flex items-center gap-1 font-medium text-foreground hover:underline">
              All actions and scopes
              <ArrowRight className="h-3 w-3" aria-hidden />
            </Link>
          ) : undefined
        }
      >
        {capability ? (
          <div className="space-y-2">
            <ActionGroup label="Write" actions={writes} />
            <ActionGroup label="Read" actions={reads} />
          </div>
        ) : null}
      </GravitreContextCard>

      <GravitreContextCard kind="Dependencies" title={agents?.length ? `${agents.length} agent${agents.length === 1 ? "" : "s"} configured with ${connector.type}` : "No agents configured with this system"}>
        {agents?.length ? (
          <ul className="space-y-1.5">
            {agents.map((agent) => (
              <li key={agent.id} className="flex items-center gap-2 text-[12.5px]">
                <AgentIdentityAvatar agent={agent} size="xs" showStatusDot={false} />
                <Link href={`/agents/${agent.id}`} className="min-w-0 truncate font-medium text-foreground hover:underline">
                  {agent.name}
                </Link>
                {agent.role ? <span className="truncate text-muted-foreground">{agent.role}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <Bot className="h-3.5 w-3.5" aria-hidden />
            Assign the system to an agent to let it act here.
          </p>
        )}
        <p className="mt-2 text-[11.5px] text-muted-foreground">Workflow usage is not reported per connector.</p>
      </GravitreContextCard>

      <GravitreContextCard kind="Activity" title={`Last sync ${connector.lastSync.toLowerCase()}`}>
        {attention ? (
          <div className="text-[12px]">
            <p className="font-medium text-foreground">{attention.problem}</p>
            <p className="mt-0.5 text-muted-foreground">{attention.evidence}</p>
            {a?.recoveryAction && a.recoveryAction !== attention.evidence ? (
              <p className="mt-1 text-muted-foreground">Recovery: {a.recoveryAction}</p>
            ) : null}
          </div>
        ) : (
          <p className="text-[12px] text-muted-foreground">No errors reported by the last check.</p>
        )}
      </GravitreContextCard>
    </aside>
  )
}

function ActionGroup({ label, actions }: { label: string; actions: ConnectorActionDefinition[] }) {
  if (!actions.length) return null
  const shown = actions.slice(0, 5)
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium text-muted-foreground">
        {label} · {actions.length}
      </p>
      <ul className="space-y-1">
        {shown.map((action) => (
          <li key={action.id} className="flex items-center justify-between gap-2 text-[12px]">
            <span className="min-w-0 truncate text-foreground">{action.name}</span>
            {action.requiresApproval ? (
              <span className="inline-flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground">
                <ShieldCheck className="h-3 w-3" aria-hidden />
                Approval
              </span>
            ) : action.destructive ? (
              <span className="shrink-0 text-[11px] text-warning">Destructive</span>
            ) : null}
          </li>
        ))}
        {actions.length > shown.length ? (
          <li className="text-[11.5px] text-muted-foreground">+{actions.length - shown.length} more</li>
        ) : null}
      </ul>
    </div>
  )
}
