"use client"

/**
 * Visual identity sections of the Carbon board: provider logo registry, agent
 * role matrix and the builder node family. Rendered from production primitives
 * (ProviderLogo, GravitreAgentIcon, builder-node-chrome); names are labelled
 * placeholders, never product claims.
 */
import type { ReactNode } from "react"
import { ShieldCheck, Users, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { PROVIDER_REGISTRY, resolveProvider, type ProviderLogoSource } from "@/lib/provider-registry"
import { GravitreAgentIcon } from "@/components/agents/fleet-v4/gravitre-agent-icon"
import { ROLE_ICON_REGISTRY } from "@/components/agents/fleet-v4/identity-tokens"
import type { AgentRoleIconId } from "@/components/agents/fleet-v4/types"
import {
  NodeHandles,
  NodeMark,
  NodeSelectionEdge,
  handleDotClass,
  nodeSurfaceClass,
  type NodeConnectState,
} from "@/components/workflows/builder-node-chrome"

const LOGO_SAMPLES = [
  "hubspot",
  "salesforce",
  "slack",
  "gmail",
  "google_drive",
  "notion",
  "github",
  "stripe",
  "snowflake",
  "zendesk",
  "intercom",
  "mailchimp",
  "linear",
  "jira",
  "figma",
  "openai",
]

const SOURCE_LABEL: Record<ProviderLogoSource, string> = {
  "simple-icons": "Simple Icons",
  "official-asset": "Official asset",
  fallback: "Fallback glyph",
}

const ROLE_ORDER: AgentRoleIconId[] = [
  "sales",
  "marketing",
  "support",
  "research",
  "data",
  "finance",
  "ops",
  "revops",
  "customer_success",
  "security",
  "developer",
  "knowledge",
  "automation",
  "general",
]

function Panel({ dark, children, className }: { dark?: boolean; children: ReactNode; className?: string }) {
  return (
    <div className={cn(dark && "dark")}>
      <div
        className={cn(
          "rounded-[8px] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-4 text-foreground",
          className,
        )}
      >
        <p className="mb-3 text-xs font-medium text-muted-foreground">{dark ? "Forced dark · Carbon 950" : "Page theme"}</p>
        {children}
      </div>
    </div>
  )
}

function LogoGrid() {
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
      {LOGO_SAMPLES.map((id) => {
        const entry = resolveProvider(id)
        return (
          <li key={id} className="flex min-w-0 items-center gap-2">
            <ProviderLogo provider={id} size="md" />
            <span className="min-w-0">
              <span className="block truncate text-[13px] text-foreground">{entry?.name ?? id}</span>
              <span className="block truncate text-[11px] text-muted-foreground">
                {entry ? SOURCE_LABEL[entry.source] : "Unregistered"}
              </span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export function ProviderLogoBoard() {
  const entries = Object.values(PROVIDER_REGISTRY)
  const counts = entries.reduce<Record<ProviderLogoSource, number>>(
    (acc, e) => ({ ...acc, [e.source]: acc[e.source] + 1 }),
    { "simple-icons": 0, "official-asset": 0, fallback: 0 },
  )
  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <LogoGrid />
        </Panel>
        <Panel dark>
          <LogoGrid />
        </Panel>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[13px] font-medium text-foreground">Registry</p>
          <dl className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-subtle)]">
            {(Object.keys(counts) as ProviderLogoSource[]).map((source) => (
              <div key={source} className="flex items-center justify-between py-2 text-[13px]">
                <dt className="text-foreground">{SOURCE_LABEL[source]}</dt>
                <dd className={TYPE.mono}>{counts[source]}</dd>
              </div>
            ))}
            <div className="flex items-center justify-between py-2 text-[13px]">
              <dt className="font-medium text-foreground">Providers</dt>
              <dd className={TYPE.mono}>{entries.length}</dd>
            </div>
          </dl>
          <p className="mt-2 text-xs text-muted-foreground">
            One registry keyed by canonical id; aliases and display names resolve to the same entry. Order: Simple Icons,
            official repo asset, neutral category glyph. No initials, no hand-drawn marks.
          </p>
        </div>
        <div>
          <p className="mb-2 text-[13px] font-medium text-foreground">Fallback and sizing</p>
          <div className="flex flex-wrap items-end gap-6">
            {(["sm", "md", "lg"] as const).map((size) => (
              <span key={size} className="flex flex-col items-center gap-1">
                <ProviderLogo provider="hubspot" size={size} />
                <span className={TYPE.mono}>{size}</span>
              </span>
            ))}
            <span className="flex flex-col items-center gap-1">
              <ProviderLogo provider="openai" size="md" />
              <span className={TYPE.mono}>no licensed mark</span>
            </span>
            <span className="flex flex-col items-center gap-1">
              <ProviderLogo provider="placeholder_unknown_vendor" label="Placeholder vendor" size="md" />
              <span className={TYPE.mono}>unregistered</span>
            </span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Fixed slot height, intrinsic aspect ratio, brand colour kept, no tile. Marks that would vanish on Carbon swap to
            their white variant; pale marks sit on an ink plate in light mode. Every mark carries its provider name as text
            alternative.
          </p>
        </div>
      </div>
    </div>
  )
}

export function RoleMatrixBoard() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {[false, true].map((dark) => (
        <Panel key={String(dark)} dark={dark}>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
            {ROLE_ORDER.map((id) => (
              <li key={id} className="flex min-w-0 items-center gap-2.5" data-board-role={id}>
                <GravitreAgentIcon icon={id} identityColor="violet" size="sm" />
                <span className="min-w-0">
                  <span className="block truncate text-[13px] text-foreground">
                    {id === "general" ? "Unknown role" : ROLE_ICON_REGISTRY[id].label}
                  </span>
                  <span className={cn(TYPE.mono, "block truncate")}>{id}</span>
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      ))}
    </div>
  )
}

function BoardNode({
  title,
  type,
  vendor,
  icon,
  selected = false,
  connectState = "idle",
  state,
  children,
  wide,
}: {
  title: string
  type: string
  vendor?: string
  icon: LucideIcon
  selected?: boolean
  connectState?: NodeConnectState
  state?: string
  children?: ReactNode
  wide?: boolean
}) {
  return (
    <div className="group/node relative" data-board-node={type}>
      <div
        className={cn(
          "relative rounded-[var(--np-radius-lg)] border p-3 shadow-[0_1px_2px_rgb(0_0_0/0.04)]",
          wide ? "w-64" : "w-56",
          nodeSurfaceClass(selected),
        )}
      >
        {selected ? <NodeSelectionEdge /> : null}
        <div className="flex items-start gap-2.5">
          <NodeMark vendor={vendor} icon={icon} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium leading-5 text-foreground">{title}</p>
            <p className="truncate text-[11px] leading-4 text-muted-foreground">{type}</p>
          </div>
          {state ? <span className="shrink-0 text-[10px] font-medium text-muted-foreground">{state}</span> : null}
        </div>
        {children}
        <NodeHandles nodeId={title} nodeName={title} selected={selected} connectState={connectState} />
      </div>
    </div>
  )
}

function CouncilSample({ selected }: { selected?: boolean }) {
  const members: { name: string; role: AgentRoleIconId }[] = [
    { name: "Placeholder A", role: "research" },
    { name: "Placeholder B", role: "finance" },
    { name: "Placeholder C", role: "security" },
  ]
  return (
    <BoardNode title="Placeholder council" type="Agent Council · 3 agents" icon={Users} selected={selected} wide>
      <ul className="mt-2.5 grid grid-cols-3 gap-1.5 border-t border-[color:var(--g-border-default)] pt-2">
        {members.map((m) => {
          const RoleIcon = ROLE_ICON_REGISTRY[m.role].Icon
          return (
            <li key={m.name} className="flex min-w-0 items-center gap-1 text-[11px] text-[color:var(--g-text-secondary)]">
              <RoleIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" strokeWidth={1.75} aria-hidden />
              <span className="truncate">{m.name.split(" ")[1]}</span>
            </li>
          )
        })}
      </ul>
      <p className="mt-1.5 text-[11px] text-muted-foreground">Consensus required · 2 evidence sources</p>
    </BoardNode>
  )
}

function NodeCanvas({ dark }: { dark?: boolean }) {
  const ResearchIcon = ROLE_ICON_REGISTRY.research.Icon as LucideIcon
  const GeneralIcon = ROLE_ICON_REGISTRY.general.Icon as LucideIcon
  return (
    <Panel dark={dark}>
      <div
        className="flex flex-wrap gap-x-8 gap-y-8 rounded-[6px] p-4"
        style={{ backgroundImage: "radial-gradient(circle, var(--g-border-strong) 1px, transparent 1.2px)", backgroundSize: "20px 20px" }}
      >
        <BoardNode title="Placeholder CRM sync" type="Connector · Update contact" vendor="hubspot" icon={GeneralIcon} />
        <BoardNode title="Placeholder researcher" type="Agent · Research" icon={ResearchIcon} selected />
        <BoardNode title="Placeholder sign-off" type="Approval · Human review" icon={ShieldCheck} state="Waiting" />
        <CouncilSample />
      </div>
    </Panel>
  )
}

function HandleStates() {
  const states: { label: string; state: NodeConnectState; selected?: boolean }[] = [
    { label: "Idle", state: "idle" },
    { label: "Selected node", state: "idle", selected: true },
    { label: "Drag source", state: "source" },
    { label: "Valid target", state: "valid" },
    { label: "Invalid (already connected)", state: "invalid" },
  ]
  return (
    <div className="flex flex-wrap items-center gap-6">
      {states.map((s) => (
        <span key={s.label} className="group/handle flex items-center gap-2 text-xs text-muted-foreground">
          <span aria-hidden className={handleDotClass(s.state, Boolean(s.selected))} />
          {s.label}
        </span>
      ))}
    </div>
  )
}

function EdgeStates() {
  const rows: { label: string; stroke: string; width: number; dash?: string }[] = [
    { label: "Edge", stroke: "var(--workflow-line-mid)", width: 1.5 },
    { label: "Edge hover", stroke: "var(--workflow-line-mid)", width: 2.25 },
    { label: "Decision path", stroke: "var(--primary)", width: 2 },
    { label: "Connection preview", stroke: "var(--signal-500)", width: 1.5, dash: "6 4" },
  ]
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.label} className="flex items-center gap-3 text-xs text-muted-foreground">
          <svg width="120" height="12" aria-hidden className="shrink-0 overflow-visible">
            <line x1="4" y1="6" x2="116" y2="6" stroke={r.stroke} strokeWidth={r.width} strokeDasharray={r.dash} strokeLinecap="round" />
            <circle cx="4" cy="6" r="3" fill={r.stroke} />
            <circle cx="116" cy="6" r="3" fill={r.stroke} />
          </svg>
          {r.label}
        </li>
      ))}
    </ul>
  )
}

export function BuilderNodeBoard() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-2">
        <NodeCanvas />
        <NodeCanvas dark />
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[13px] font-medium text-foreground">Handles</p>
          <HandleStates />
          <p className="mt-2 text-xs text-muted-foreground">
            8px dot in a 20px hit area (24px on touch). Side handles always visible; top and bottom reveal on hover, focus
            or selection.
          </p>
        </div>
        <div>
          <p className="mb-2 text-[13px] font-medium text-foreground">Edges</p>
          <EdgeStates />
          <p className="mt-2 text-xs text-muted-foreground">
            Edges end on the handle centre. Glow and moving dots only while a real run is active.
          </p>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        One rectangular family: mark, title, &ldquo;Type · role/action&rdquo;, state. Selected = Signal border, 2px Signal edge,
        Graphite 800 in dark. Council is a wider member of the same family — no circles, rings or orbits. Decision keeps
        its diamond as the branching exception.
      </p>
    </div>
  )
}
