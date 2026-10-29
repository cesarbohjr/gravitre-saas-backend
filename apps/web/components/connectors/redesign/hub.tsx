"use client"

import { useMemo, useState, type ReactNode } from "react"
import Link from "next/link"
import useSWR from "swr"
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Bot,
  Check,
  ChevronRight,
  Download,
  LayoutList,
  Loader2,
  Network,
  Search,
  Workflow as WorkflowIcon,
  X,
  Zap,
} from "lucide-react"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import type { ConnectorAgentRef, ConnectorAttention, VendorCapability } from "@/components/connectors/connector-operating"
import { CONNECTOR_DEPARTMENTS, type ConnectorDepartmentId } from "@/components/connectors/department-filter"
import { toast } from "@/components/connectors/overlays/toast"
import { knowledgeSyncApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { listAvailableConnectors, connectorVendorKey, type CatalogConnectorEntry } from "@/lib/connectors"
import { KNOWLEDGE_SYNC_KEY, sourceStatusMeta, type KnowledgeSource, type KnowledgeSyncOverview } from "@/lib/settings-api/enterprise"
import type { Workflow } from "@/types/api"
import { FirstRunArt, HubHeroArt, StarterSetArt, StarterSetIcon, VendorTile, type StarterDept } from "./art"
import { relativeTime, usageSentence, type PlayRef } from "./connector-usage"
import { coverFor } from "./vendor-look"

export type HubConnector = {
  id: string
  name: string
  type: string
  vendorKey: string
  status: "connected" | "disconnected" | "error" | "syncing"
  environment: "production" | "staging"
  lastSync: string
  lastSyncAt?: string | null
  createdAt?: string | null
  category?: string
  authType?: "oauth" | "apiKey" | "webhook"
  authStatus?: string
  blockingReason?: string
  availability?: {
    configured: boolean
    authenticated: boolean
    tokenValid: boolean
    scopesValid: boolean
    healthy: boolean
    executable: boolean
    blockingReason?: string
    lastCheckedAt?: string
  }
}

export type HubStatusFilter = "all" | "connected" | "syncing" | "attention" | "offline"

/** Which status tab a connector counts under; attention wins over the raw status. */
export function hubStatusOf(connector: HubConnector, attention: boolean): Exclude<HubStatusFilter, "all"> {
  if (attention || connector.status === "error") return "attention"
  if (connector.status === "syncing") return "syncing"
  if (connector.status === "connected") return "connected"
  return "offline"
}

const STATUS_PILL: Record<Exclude<HubStatusFilter, "all">, { cls: string; label: string }> = {
  connected: { cls: "connected", label: "Connected" },
  syncing: { cls: "syncing", label: "Syncing" },
  attention: { cls: "attention", label: "Needs attention" },
  offline: { cls: "offline", label: "Offline" },
}

export function StatusPill({ status, label }: { status: Exclude<HubStatusFilter, "all">; label?: string }) {
  const pill = STATUS_PILL[status]
  return (
    <span className={`cn-pill ${pill.cls}`}>
      <span className="d" aria-hidden />
      {label ?? pill.label}
    </span>
  )
}

/** "Read and write · 14 actions" from the capability catalog; "" when the catalog has nothing for it. */
export function accessLabel(capability: VendorCapability | undefined): string {
  if (!capability) return ""
  const total = capability.actions.length
  if (total === 0) return ""
  const kind = capability.write > 0 ? (capability.read > 0 ? "Read and write" : "Write") : "Read only"
  return `${kind} · ${total} ${total === 1 ? "action" : "actions"}`
}

function categoryLabel(connector: HubConnector): string {
  return coverFor(connector.vendorKey || connector.type, connector.category).label
}

/* ------------------------------------------------------------------ Hero */

export function HubHero({
  connectors,
  readyCount,
  syncingCount,
  attentionCount,
  playsWaiting,
  playsLoaded,
  checkedAt,
  refreshing,
  onRefresh,
  onAdd,
  onFilter,
}: {
  connectors: HubConnector[]
  readyCount: number
  syncingCount: number
  attentionCount: number
  playsWaiting: number
  playsLoaded: boolean
  checkedAt: number | null
  refreshing: boolean
  onRefresh: () => void
  onAdd: () => void
  onFilter: (filter: HubStatusFilter) => void
}) {
  const total = connectors.length
  // The three tiles in the art stand for the first three systems, in hub order: ready, needs attention, or not there yet.
  const tiles = [0, 1, 2].map((index) => {
    const c = connectors[index]
    if (!c) return "empty" as const
    return c.availability ? (c.availability.executable ? ("ok" as const) : ("bad" as const)) : c.status === "connected" ? ("ok" as const) : ("bad" as const)
  }) as ["ok" | "bad" | "empty", "ok" | "bad" | "empty", "ok" | "bad" | "empty"]
  return (
    <section aria-labelledby="cn-title" className="cn-card cn-hero">
      <div className="cn-hero-art">
        <HubHeroArt tiles={tiles} />
        <div className="cn-hero-chip">
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flex: 1, minWidth: 0 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: readyCount > 0 ? "#19C37D" : "#8A8B85" }} aria-hidden />
            {readyCount} of {total} ready for agents
          </span>
          <button type="button" className="gv-btn outline sm" onClick={() => onFilter("connected")}>
            Show ready
          </button>
        </div>
      </div>
      <div className="cn-hero-body">
        <div className="cn-crumbs">
          <span className="cn-eyebrow">Integrate / Connectors</span>
          <button
            type="button"
            className={`cn-live${checkedAt ? "" : " stale"}`}
            onClick={onRefresh}
            disabled={refreshing}
            title="Check live status now"
          >
            {refreshing ? <Loader2 size={12} className="cno-spin" aria-hidden /> : <span className="d" aria-hidden />}
            {refreshing ? "Checking live status" : checkedAt ? `Live · checked ${relativeTime(new Date(checkedAt).toISOString())}` : "Not checked yet"}
          </button>
        </div>
        <h1 id="cn-title" className="cn-h1">
          Connectors
        </h1>
        <p className="cn-lede">
          The systems your agents, workflows and plays act on. Each one moves from connected, to authorized, to granted the
          permissions it needs, to ready for agents.
        </p>
        <div className="cn-tiles">
          <button type="button" className="cn-tile good" onClick={() => onFilter("connected")}>
            <span className="v">{readyCount}</span>
            <span className="l">Ready for agents</span>
          </button>
          <button type="button" className="cn-tile" onClick={() => onFilter("syncing")}>
            <span className="v">{syncingCount}</span>
            <span className="l">Syncing now</span>
          </button>
          <button type="button" className={`cn-tile ${attentionCount > 0 ? "bad" : ""}`} onClick={() => onFilter("attention")}>
            <span className="v">{attentionCount}</span>
            <span className="l">Need attention</span>
          </button>
          <Link href="/plays" className={`cn-tile ${playsWaiting > 0 ? "warn" : ""}`} style={{ textDecoration: "none" }}>
            <span className="v">{playsLoaded ? playsWaiting : "–"}</span>
            <span className="l">Plays waiting on a connector</span>
          </Link>
        </div>
        <div className="cn-row-flex">
          <button type="button" className="gv-btn dark" onClick={onAdd}>
            Add connector
          </button>
          <button type="button" className="gv-btn outline" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? <Loader2 size={15} className="cno-spin" aria-hidden /> : null}
            Check live status
          </button>
          <AskGravitreSummonButton
            className="cn-btn-text"
            label="Ask Gravitre what to connect"
            prompt="Which systems should I connect next so my agents and plays can do more?"
          />
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------ Fabric */

export type FabricPhase = { id: string; label: string; hint: string; count: number | null; tone: "neutral" | "done" | "live" | "risk" }

export function CapabilityFabric({ phases, total }: { phases: FabricPhase[]; total: number }) {
  return (
    <section className="cn-card cn-fabric" aria-label="Capability fabric">
      <div className="cn-row-flex">
        <span className="cn-eyebrow">Capability fabric</span>
        <span className="cn-sub" style={{ margin: 0 }}>
          How far each system has come
        </span>
      </div>
      <div className="cn-phases">
        {phases.map((phase) => {
          const pct = phase.count == null || total === 0 ? 0 : Math.round((phase.count / total) * 100)
          return (
            <div key={phase.id} className={`cn-phase ${phase.tone}`}>
              <span className="n">{phase.count ?? "–"}</span>
              <span className="l">{phase.label}</span>
              <span className="h">{phase.hint}</span>
              <span className="bar" aria-hidden>
                <i style={{ width: `${phase.tone === "neutral" ? 100 : pct}%` }} />
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

/* ----------------------------------------------------------- Filters */

export function HubFilters({
  status,
  onStatus,
  counts,
  query,
  onQuery,
  department,
  onDepartment,
  view,
  onView,
}: {
  status: HubStatusFilter
  onStatus: (value: HubStatusFilter) => void
  counts: Record<HubStatusFilter, number>
  query: string
  onQuery: (value: string) => void
  department: ConnectorDepartmentId | null
  onDepartment: (value: ConnectorDepartmentId | null) => void
  view: "list" | "topology"
  onView: (value: "list" | "topology") => void
}) {
  const tabs: Array<{ id: HubStatusFilter; label: string; dot?: string }> = [
    { id: "all", label: "All" },
    { id: "connected", label: "Connected", dot: "#19C37D" },
    { id: "syncing", label: "Syncing", dot: "#2B59E0" },
    { id: "attention", label: "Needs attention", dot: "#A3333D" },
    { id: "offline", label: "Offline", dot: "#8A8B85" },
  ]
  return (
    <nav aria-label="Connector filters" className="cn-filters">
      <div className="cn-seg" role="group" aria-label="Status">
        {tabs.map((tab) => (
          <button key={tab.id} type="button" aria-pressed={status === tab.id} onClick={() => onStatus(tab.id)}>
            {tab.dot ? <span style={{ width: 7, height: 7, borderRadius: "50%", background: tab.dot }} aria-hidden /> : null}
            {tab.label}
            <span className={`n${tab.id === "attention" && counts.attention > 0 ? " bad" : ""}`}>{counts[tab.id]}</span>
          </button>
        ))}
      </div>
      <label className="gv-field cn-search">
        <Search size={16} aria-hidden />
        <input aria-label="Search connectors" placeholder="Search connectors" value={query} onChange={(e) => onQuery(e.target.value)} />
        {query ? (
          <button type="button" className="cn-iconbtn" style={{ width: 28, height: 28 }} aria-label="Clear search" onClick={() => onQuery("")}>
            <X size={14} aria-hidden />
          </button>
        ) : null}
      </label>
      <label className="cn-row-flex" style={{ gap: 8, fontSize: 13, color: "var(--gv-muted)" }}>
        Department
        <select
          className="cn-select"
          value={department ?? ""}
          onChange={(e) => onDepartment((e.target.value || null) as ConnectorDepartmentId | null)}
        >
          <option value="">All departments</option>
          {CONNECTOR_DEPARTMENTS.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
            </option>
          ))}
        </select>
      </label>
      <div className="cn-seg" role="group" aria-label="View" style={{ marginLeft: "auto" }}>
        <button type="button" aria-pressed={view === "list"} onClick={() => onView("list")}>
          <LayoutList size={15} aria-hidden />
          List
        </button>
        <button type="button" aria-pressed={view === "topology"} onClick={() => onView("topology")}>
          <Network size={15} aria-hidden />
          Topology
        </button>
      </div>
    </nav>
  )
}

/* --------------------------------------------------------- Attention */

const ATTENTION_TAG: Record<ConnectorAttention["kind"], string> = {
  expired: "Authorization expired",
  scope: "Missing permission",
  unauthorized: "Not authorized",
  failing: "Failing checks",
}

export function AttentionCard({
  items,
  unlock,
  onAction,
}: {
  items: ConnectorAttention[]
  /** "Fix these and 2 more systems can take actions, and 9 plays unlock". */
  unlock: string
  onAction: (item: ConnectorAttention) => void
}) {
  if (items.length === 0) return null
  return (
    <section className="cn-card" aria-labelledby="cn-att-h">
      <div className="cn-cardhead">
        <span className="cn-ico sm bad" aria-hidden>
          <AlertTriangle size={16} />
        </span>
        <div style={{ flex: "1 1 200px" }}>
          <div id="cn-att-h" style={{ fontWeight: 600 }}>
            Needs your attention
          </div>
          <div className="cn-sub">{unlock}</div>
        </div>
      </div>
      {items.map((item) => (
        <div key={item.connector.id} className="cn-attn">
          <VendorTile vendor={item.connector.vendorKey || item.connector.type} category={item.connector.category} />
          <div className="body">
            <div className="title">
              <span>{item.connector.name}</span>
              <span className="cn-pill attention">{ATTENTION_TAG[item.kind]}</span>
            </div>
            <p>{item.evidence}</p>
          </div>
          <button type="button" className="gv-btn dark sm" onClick={() => onAction(item)}>
            {item.actionLabel}
          </button>
        </div>
      ))}
    </section>
  )
}

/* ------------------------------------------------------------- Table */

export type HubRow = {
  connector: HubConnector
  status: Exclude<HubStatusFilter, "all">
  statusLabel: string
  access: string
  usedBy: string
}

export function SystemsTable({
  title,
  rows,
  selectedId,
  onSelect,
  menu,
  onExport,
}: {
  title: string
  rows: HubRow[]
  selectedId: string | null
  onSelect: (connector: HubConnector, target: HTMLElement) => void
  menu: (connector: HubConnector) => ReactNode
  onExport: () => void
}) {
  return (
    <section className="cn-card" aria-labelledby="cn-sys-h" style={{ overflow: "hidden" }}>
      <div className="cn-cardhead">
        <div style={{ flex: "1 1 200px" }}>
          <h2 id="cn-sys-h" className="cn-h2" style={{ fontSize: 15 }}>
            {title}
          </h2>
          <div className="cn-sub">{rows.length} shown · select a row to inspect</div>
        </div>
        <button type="button" className="gv-btn outline sm" onClick={onExport} disabled={rows.length === 0}>
          <Download size={14} aria-hidden />
          Export
        </button>
      </div>
      <div className="cn-tblwrap">
        <div className="cn-tbl" role="table" aria-label={title}>
          <div className="cn-tr head" role="row">
            {["Connector", "Status", "Access", "Used by", "Last sync", ""].map((h, i) => (
              <span key={i} className="cn-th" role="columnheader">
                {h}
              </span>
            ))}
          </div>
          {rows.map((row) => {
            const c = row.connector
            const selected = selectedId === c.id
            return (
              <div
                key={c.id}
                role="row"
                tabIndex={0}
                aria-selected={selected}
                className="cn-tr body"
                onClick={(e) => {
                  if ((e.target as HTMLElement).closest("[data-row-menu]")) return
                  onSelect(c, e.currentTarget)
                }}
                onKeyDown={(e) => {
                  if (e.target !== e.currentTarget) return
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    onSelect(c, e.currentTarget)
                  }
                }}
              >
                <span className="cn-td" role="cell" style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <VendorTile vendor={c.vendorKey || c.type} category={c.category} />
                  <span style={{ minWidth: 0 }}>
                    <span className="cn-ellip" style={{ display: "block", fontWeight: 600, fontSize: 14 }}>
                      {c.name}
                    </span>
                    <span className="cn-ellip" style={{ display: "block", fontSize: 12, color: "var(--gv-muted)" }}>
                      {categoryLabel(c)}
                      {c.environment === "staging" ? " · Staging" : ""}
                    </span>
                  </span>
                </span>
                <span className="cn-td" role="cell">
                  <StatusPill status={row.status} label={row.statusLabel} />
                </span>
                <span className="cn-td cn-ellip" role="cell" data-label="Access" style={{ color: "var(--gv-text-2)" }}>
                  {row.access || "–"}
                </span>
                <span className="cn-td cn-ellip" role="cell" data-label="Used by" style={{ color: "var(--gv-text-2)" }}>
                  {row.usedBy || "Not used yet"}
                </span>
                <span className="cn-td cn-mono" role="cell" data-label="Last sync" style={{ color: "var(--gv-muted)", fontSize: 12.5 }}>
                  {c.lastSyncAt ? relativeTime(c.lastSyncAt) : c.lastSync}
                </span>
                <span className="cn-td" role="cell" data-row-menu style={{ padding: "0 6px" }}>
                  {menu(c)}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}

/** Downloads the rows on screen as CSV. Nothing is fetched; it is exactly what the table shows. */
export function exportRowsCsv(rows: HubRow[]) {
  const header = ["Name", "Vendor", "Category", "Environment", "Status", "Access", "Used by", "Last sync"]
  const lines = rows.map((row) =>
    [
      row.connector.name,
      row.connector.type,
      categoryLabel(row.connector),
      row.connector.environment,
      row.statusLabel,
      row.access,
      row.usedBy,
      row.connector.lastSyncAt ?? row.connector.lastSync,
    ]
      .map((v) => csvCell(String(v ?? "")))
      .join(","),
  )
  const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `connectors-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/* --------------------------------------------------------- Inspector */

function ReadyRow({ ok, wait, label, value, strong }: { ok: boolean; wait?: boolean; label: string; value: string; strong?: boolean }) {
  const state = ok ? "ok" : wait ? "wait" : "bad"
  return (
    <li>
      <span className={`cn-check ${state}`} aria-hidden>
        {ok ? <Check size={13} strokeWidth={2.6} /> : wait ? <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} /> : <X size={13} strokeWidth={2.6} />}
      </span>
      <span style={{ flex: 1, fontWeight: strong ? 600 : undefined }}>{label}</span>
      <span className={`r${state === "bad" ? " bad" : ""}`}>{value}</span>
    </li>
  )
}

export function HubInspector({
  connector,
  statusLabel,
  capability,
  agents,
  workflows,
  plays,
  attention,
  onReconnect,
  onConfigure,
  onTest,
  onSync,
  onClose,
}: {
  connector: HubConnector
  statusLabel: string
  capability?: VendorCapability
  agents: ConnectorAgentRef[]
  workflows: Workflow[]
  plays: PlayRef[]
  attention: ConnectorAttention | null
  onReconnect?: () => void
  onConfigure: () => void
  onTest: () => Promise<void> | void
  onSync: () => Promise<void> | void
  onClose: () => void
}) {
  const [testing, setTesting] = useState(false)
  const a = connector.availability
  const deptLabel = CONNECTOR_DEPARTMENTS.find((d) => d.categories.includes(connector.category ?? ""))?.label
  const created = connector.createdAt ? new Date(connector.createdAt) : null
  const usedBy = usageSentence(agents.length, workflows.length)
  const scopes = capability ? new Set(capability.actions.flatMap((x) => x.scopes ?? [])).size : 0
  const primary = attention
    ? attention.action === "reconnect" && onReconnect
      ? { label: `Reconnect ${connector.type}`, run: onReconnect }
      : attention.action === "configure"
        ? { label: attention.actionLabel, run: onConfigure }
        : null
    : null
  return (
    <section className="cn-card cn-pad" aria-label={`${connector.name} details`}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <VendorTile vendor={connector.vendorKey || connector.type} category={connector.category} size="md" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="cn-ellip" style={{ fontWeight: 600, fontSize: 16 }}>
            {connector.name}
          </div>
          <div className="cn-ellip" style={{ fontSize: 12, color: "var(--gv-muted)" }}>
            {[categoryLabel(connector), deptLabel, connector.environment === "staging" ? "Staging" : "Production"].filter(Boolean).join(" · ")}
          </div>
        </div>
        <button type="button" className="cn-iconbtn" aria-label="Close inspector" onClick={onClose}>
          <X size={16} aria-hidden />
        </button>
      </div>
      {attention ? (
        <div className="cn-alert bad">
          <AlertTriangle size={16} style={{ flex: "0 0 auto", marginTop: 2 }} aria-hidden />
          <span>
            {attention.evidence}
            {usedBy ? ` ${usedBy} use ${connector.type}.` : ""}
          </span>
        </div>
      ) : null}
      <div className="cn-eyebrow" style={{ marginTop: 4 }}>
        Readiness
      </div>
      {a ? (
        <ul className="cn-ready" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          <ReadyRow
            ok={a.configured}
            label="Connected"
            value={a.configured ? (created ? created.toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "Yes") : "Setup needed"}
          />
          <ReadyRow
            ok={a.authenticated && a.tokenValid}
            strong={!(a.authenticated && a.tokenValid)}
            label="Authorized"
            value={!a.authenticated ? "Not signed in" : a.tokenValid ? "Valid" : "Expired"}
          />
          <ReadyRow
            ok={a.scopesValid}
            label="Permissions granted"
            value={a.scopesValid ? (scopes ? `${scopes} scopes` : "Granted") : "Missing"}
          />
          <ReadyRow ok={a.executable} wait={!a.executable} label="Agents can act" value={a.executable ? "Yes" : "Paused"} />
        </ul>
      ) : (
        <p className="cn-sub" style={{ margin: 0 }}>
          {statusLabel}. Run a live check to see each readiness step.
        </p>
      )}
      <div className="cn-mini" style={{ flexDirection: "column", alignItems: "stretch", gap: 4 }}>
        <div className="cn-eyebrow">Used by</div>
        {agents.length + workflows.length + plays.length === 0 ? (
          <p className="cn-sub" style={{ margin: "4px 0 0" }}>
            No agents, workflows or plays use {connector.type} yet.
          </p>
        ) : (
          <ul className="cn-uses">
            {agents.slice(0, 4).map((agent) => (
              <li key={`a${agent.id}`}>
                <Link href={`/agents/${agent.id}`}>
                  <span className="cn-ico sm blue" style={{ width: 26, height: 26, borderRadius: 8 }} aria-hidden>
                    <Bot size={14} />
                  </span>
                  <span className="cn-ellip">{agent.name}</span>
                </Link>
              </li>
            ))}
            {workflows.slice(0, 3).map((w) => (
              <li key={`w${w.id}`}>
                <Link href={`/workflows/${w.id}`}>
                  <span className="cn-ico sm" style={{ width: 26, height: 26, borderRadius: 8 }} aria-hidden>
                    <WorkflowIcon size={14} />
                  </span>
                  <span className="cn-ellip">{w.name} · workflow</span>
                </Link>
              </li>
            ))}
            {plays.slice(0, 3).map((p) => (
              <li key={`p${p.key}`}>
                <Link href={`/plays/${p.key}`}>
                  <span className="cn-ico sm warn" style={{ width: 26, height: 26, borderRadius: 8 }} aria-hidden>
                    <Zap size={14} />
                  </span>
                  <span className="cn-ellip">
                    {p.name} · play{p.waiting ? ", waiting" : ""}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="cn-row-flex" style={{ gap: 8, paddingTop: 4 }}>
        {primary ? (
          <button type="button" className="gv-btn green sm" style={{ flex: "1 1 auto" }} onClick={primary.run}>
            {primary.label}
          </button>
        ) : (
          <button type="button" className="gv-btn green sm" style={{ flex: "1 1 auto" }} onClick={() => void onSync()}>
            Sync now
          </button>
        )}
        <button
          type="button"
          className="gv-btn outline sm"
          disabled={testing}
          onClick={async () => {
            setTesting(true)
            try {
              await onTest()
            } finally {
              setTesting(false)
            }
          }}
        >
          {testing ? <Loader2 size={14} className="cno-spin" aria-hidden /> : null}
          Test
        </button>
        <button type="button" className="gv-btn outline sm" onClick={onConfigure}>
          Configure
        </button>
      </div>
      <Link href={`/connectors/${connector.id}`} className="cn-btn-text sm" style={{ alignSelf: "flex-start" }}>
        Open full details <ArrowRight size={14} aria-hidden />
      </Link>
    </section>
  )
}

/** Shown in the side column when no row is picked: the next thing worth doing. */
export function HubSideSummary({ readyCount, total, attention, onPick }: { readyCount: number; total: number; attention: ConnectorAttention[]; onPick: (id: string) => void }) {
  return (
    <section className="cn-card cn-pad">
      <div className="cn-eyebrow">Inspector</div>
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5 }}>
        {readyCount} of {total} systems can take actions. Select a row to see its readiness, what uses it and what to do next.
      </p>
      {attention[0] ? (
        <button type="button" className="cn-btn-text sm" style={{ alignSelf: "flex-start", padding: 0 }} onClick={() => onPick(attention[0].connector.id)}>
          Start with {attention[0].connector.name} <ChevronRight size={14} aria-hidden />
        </button>
      ) : null}
    </section>
  )
}

/* ---------------------------------------------------- Knowledge sync */

const SOURCE_PILL: Record<string, string> = { green: "connected", blue: "syncing", red: "attention", neutral: "neutral", amber: "amber" }

export function KnowledgeCard({ isAdmin }: { isAdmin: boolean }) {
  const { data, mutate } = useSWR<KnowledgeSyncOverview>(KNOWLEDGE_SYNC_KEY, fetcher, { revalidateOnFocus: false })
  const [busy, setBusy] = useState<string | null>(null)
  const sources = data?.sources ?? []
  if (!data) return null
  const blocked = Boolean(data.ingestionDisabled || data.heldReason)

  const run = async (source: KnowledgeSource) => {
    setBusy(source.connectorId)
    try {
      await knowledgeSyncApi.triggerConnectorSync(source.connectorId, { fullSync: false })
      toast.success(`${source.name} synced to Knowledge`, { vendor: source.type, topic: "Knowledge" })
      await mutate()
    } catch (err) {
      toast.error(`${source.name} did not sync`, {
        vendor: source.type,
        topic: "Knowledge",
        description: err instanceof Error ? err.message : "Try again in a moment.",
      })
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="cn-card cn-pad" aria-labelledby="cn-ks-h">
      <div className="cn-row-flex" style={{ fontWeight: 600 }}>
        <span className="cn-ico sm blue" aria-hidden>
          <BookOpen size={15} />
        </span>
        <span id="cn-ks-h">Knowledge sync</span>
      </div>
      <p className="cn-sub" style={{ margin: 0, lineHeight: 1.5 }}>
        Content these systems feed into Knowledge, so agents can cite it.
        {blocked ? " Ingestion is paused for this workspace." : ""}
      </p>
      {sources.length === 0 ? (
        <p className="cn-sub" style={{ margin: 0 }}>
          No connected system feeds Knowledge yet.
        </p>
      ) : (
        sources.slice(0, 5).map((source) => {
          const meta = sourceStatusMeta(source.status)
          const canRun = isAdmin && !blocked && !source.heldReason && (meta.cta === "Sync now" || meta.cta === "Retry")
          const detail =
            source.status === "syncing"
              ? "Syncing now"
              : source.lastSyncAt
                ? `${source.docs14d.toLocaleString()} docs in 14 days · synced ${relativeTime(source.lastSyncAt)}`
                : source.status === "not_configured"
                  ? "Not synced to Knowledge"
                  : "Never synced"
          return (
            <div key={source.connectorId} className="cn-mini">
              <VendorTile vendor={source.type} size="sm" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="cn-ellip" style={{ fontSize: 14, fontWeight: 500 }}>
                  {source.name}
                </div>
                <div className="cn-ellip" style={{ fontSize: 12, color: "var(--gv-muted)" }}>
                  {detail}
                </div>
              </div>
              {canRun && source.status !== "healthy" ? (
                <button type="button" className="cn-btn-text sm" disabled={busy === source.connectorId} onClick={() => void run(source)}>
                  {busy === source.connectorId ? <Loader2 size={13} className="cno-spin" aria-hidden /> : null}
                  {meta.cta === "Retry" ? "Retry" : "Turn on"}
                </button>
              ) : (
                <span className={`cn-pill ${SOURCE_PILL[meta.tone] ?? "neutral"}`}>{source.status === "healthy" ? "On" : meta.label}</span>
              )}
            </div>
          )
        })
      )}
      {isAdmin ? (
        <a href="#knowledge-sync" className="cn-btn-text sm" style={{ alignSelf: "flex-start", padding: 0 }}>
          All sources and sync history <ArrowRight size={14} aria-hidden />
        </a>
      ) : null}
    </section>
  )
}

/* --------------------------------------------------------- First run */

/** The systems each starter set suggests first, in order; only shipped connectors are kept. */
const STARTER_VENDORS: Record<StarterDept, string[]> = {
  sales: ["hubspot", "apollo", "gmail", "salesforce", "slack"],
  marketing: ["google_search_console", "google_analytics", "google_ads", "marketo", "hubspot"],
  finance: ["quickbooks", "xero", "netsuite", "stripe"],
  support: ["zendesk", "slack", "notion", "intercom", "freshservice"],
  operations: ["jira", "monday", "slack", "asana", "notion"],
  engineering: ["github", "jira", "pagerduty", "confluence"],
}

const STARTER_PITCH: Record<StarterDept, string> = {
  sales: "Enrich leads and keep the pipeline moving",
  marketing: "Watch rankings, campaigns and traffic",
  finance: "Read cash position and chase invoices",
  support: "Triage tickets and draft answers",
  operations: "Track vendor spend and coordinate work",
  engineering: "Follow incidents, issues and code changes",
}

export type StarterSet = { dept: StarterDept; label: string; apps: CatalogConnectorEntry[]; agents: number; pitch: string }

export function useStarterSets(agentsByVendor: Map<string, ConnectorAgentRef[]>): StarterSet[] {
  return useMemo(() => {
    const shipped = listAvailableConnectors()
    const byKey = new Map(shipped.map((entry) => [entry.vendorKey, entry]))
    return CONNECTOR_DEPARTMENTS.map((d) => {
      const dept = d.id as StarterDept
      const picks: CatalogConnectorEntry[] = []
      for (const key of STARTER_VENDORS[dept] ?? []) {
        const entry = byKey.get(key)
        if (entry && !picks.includes(entry)) picks.push(entry)
        if (picks.length === 3) break
      }
      for (const entry of shipped) {
        if (picks.length >= 3) break
        if (d.categories.includes(entry.category) && !picks.includes(entry)) picks.push(entry)
      }
      const agentIds = new Set<string>()
      for (const entry of picks) for (const agent of agentsByVendor.get(connectorVendorKey(entry.vendorKey)) ?? []) agentIds.add(agent.id)
      return { dept, label: d.label, apps: picks, agents: agentIds.size, pitch: STARTER_PITCH[dept] }
    }).filter((set) => set.apps.length > 0)
  }, [agentsByVendor])
}

export function FirstRun({ sets, onAdd }: { sets: StarterSet[]; onAdd: (preset?: string) => void }) {
  return (
    <>
      <section className="cn-card cn-hero" style={{ alignItems: "center" }}>
        <div style={{ flex: "1 1 360px", maxWidth: 460, aspectRatio: "320 / 200", borderRadius: 14, overflow: "hidden", border: "1px solid var(--gv-border)" }}>
          <FirstRunArt />
        </div>
        <div className="cn-hero-body" style={{ flex: "1 1 360px" }}>
          <div className="cn-eyebrow">Connectors · get started</div>
          <h1 className="cn-h1">Connect your first system</h1>
          <p className="cn-lede">
            Connectors are what your agents and workflows can act on. Each one moves through four steps, and nothing writes to
            your apps until you say so.
          </p>
          <ol className="cn-path">
            <li>
              <span className="cn-pn">1</span>Connect a system
            </li>
            <li>
              <span className="cn-pn">2</span>Authorize access
            </li>
            <li>
              <span className="cn-pn">3</span>Grant the permissions agents need
            </li>
            <li>
              <span className="cn-pn go">4</span>Agents can act, with approvals on
            </li>
          </ol>
          <div className="cn-row-flex">
            <button type="button" className="gv-btn dark" onClick={() => onAdd()}>
              Add your first connector
            </button>
            <AskGravitreSummonButton
              className="gv-btn outline"
              label="Ask Gravitre what to connect"
              prompt="Which system should I connect first, given my agents and goals?"
            />
          </div>
        </div>
      </section>
      <div className="cn-row-flex" style={{ alignItems: "baseline", gap: "6px 12px" }}>
        <h2 className="cn-h2" style={{ fontSize: 18 }}>
          Start with a team
        </h2>
        <span className="cn-sub" style={{ margin: 0 }}>
          We suggest the systems that team&apos;s agents use most
        </span>
      </div>
      <div className="cn-grid3">
        {sets.map((set) => (
          <StarterSetCard key={set.dept} set={set} onConnect={() => onAdd(set.apps[0]?.type)} />
        ))}
      </div>
    </>
  )
}

function StarterSetCard({ set, onConnect }: { set: StarterSet; onConnect: () => void }) {
  return (
    <button type="button" className="cn-card cn-mcard" onClick={onConnect} style={{ textAlign: "left", font: "inherit", padding: 0, cursor: "pointer" }}>
      <div className="art">
        <StarterSetArt dept={set.dept} />
        <span className="count">
          {set.apps.length} {set.apps.length === 1 ? "app" : "apps"}
        </span>
      </div>
      <div style={{ padding: "14px 16px 0", display: "flex", gap: 12, alignItems: "center" }}>
        <StarterSetIcon dept={set.dept} />
        <span style={{ display: "flex", flexDirection: "column", minWidth: 0, gap: 2 }}>
          <span style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.25 }}>{set.label} starter set</span>
          <span className="cn-ellip" style={{ fontSize: 12.5, color: "var(--gv-muted)" }}>
            {set.apps.map((a) => a.type).join(", ")}
          </span>
        </span>
      </div>
      <div className="body" style={{ paddingTop: 10 }}>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.45, color: "var(--gv-muted)" }}>{set.pitch}</p>
        <div className="cn-row-flex" style={{ gap: 6 }}>
          <span className="cn-chip dark">Connectors</span>
          <span className="cn-chip">{set.label}</span>
          <span className="cn-chip" style={{ background: "var(--gv-soft)", border: 0 }}>
            {set.agents === 0 ? "No agents yet" : `${set.agents} ${set.agents === 1 ? "agent" : "agents"} ready`}
          </span>
        </div>
      </div>
      <div className="foot">
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#E2A33A", flex: "0 0 auto" }} aria-hidden />
        <span style={{ flex: 1, minWidth: 0 }}>Not connected yet</span>
        <span className="gv-btn green sm">Connect</span>
      </div>
    </button>
  )
}
