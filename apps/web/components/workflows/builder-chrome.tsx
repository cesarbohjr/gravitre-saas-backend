"use client"

import type { ComponentType, ReactNode } from "react"
import Link from "next/link"
import {
  Activity,
  Bot,
  CalendarClock,
  Database,
  ExternalLink,
  History,
  Layers,
  PenLine,
  Plug,
  Plus,
  Share2,
  ShieldCheck,
  Store,
  Workflow,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

type IconType = ComponentType<{ className?: string }>

type BuilderNavItem = { label: string; href: string; icon: IconType; current?: boolean }

/**
 * Builder-local navigation. Every destination is an existing route; nothing here
 * links to a surface the product does not already ship.
 */
export function BuilderNav({ workflowId }: { workflowId: string }) {
  const groups: { label: string; items: BuilderNavItem[] }[] = [
    {
      label: "Workflow",
      items: [
        { label: "Editor", href: `/workflows/${workflowId}/builder`, icon: PenLine, current: true },
        { label: "Runs", href: "/runs", icon: History },
        { label: "Approvals", href: "/approvals", icon: ShieldCheck },
        { label: "Monitoring", href: "/activity", icon: Activity },
        { label: "Schedules", href: "/schedules", icon: CalendarClock },
      ],
    },
    {
      label: "Resources",
      items: [
        { label: "Agents", href: "/agents", icon: Bot },
        { label: "Sources", href: "/sources", icon: Database },
        { label: "Environments", href: "/environments", icon: Layers },
      ],
    },
    {
      label: "Build",
      items: [
        { label: "Workflows", href: "/workflows", icon: Workflow },
        { label: "Marketplace", href: "/marketplace/assets", icon: Store },
      ],
    },
    {
      label: "Developer",
      items: [
        { label: "Connectors", href: "/connectors", icon: Plug },
        { label: "Integrations", href: "/integrations", icon: Share2 },
      ],
    },
  ]

  return (
    <nav
      aria-label="Workflow builder"
      data-review-surface="builder-nav"
      className="hidden shrink-0 flex-col gap-4 overflow-y-auto border-r border-[color:var(--g-border-subtle)] bg-[color:var(--g-chrome)] py-3 lg:flex lg:w-12 xl:w-52"
    >
      {groups.map((group) => (
        <div key={group.label} className="flex flex-col gap-0.5 px-1.5 xl:px-2">
          <p className="hidden px-2 pb-1 text-xs font-medium text-muted-foreground xl:block">{group.label}</p>
          {group.items.map((item) => {
            const Icon = item.icon
            return (
              <Link
                key={item.label}
                href={item.href}
                aria-current={item.current ? "page" : undefined}
                title={item.label}
                className={cn(
                  "relative flex h-8 items-center gap-2.5 rounded-[5px] px-2 text-[13px] font-medium transition-colors",
                  "justify-center xl:justify-start",
                  item.current
                    ? "bg-[color:var(--g-surface-3)] text-foreground before:absolute before:inset-y-1.5 before:left-0 before:w-[2px] before:rounded-full before:bg-[color:var(--g-brand)] before:content-['']"
                    : "text-muted-foreground hover:bg-[color:var(--g-chrome-hover)] hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="sr-only xl:not-sr-only xl:truncate">{item.label}</span>
              </Link>
            )
          })}
        </div>
      ))}
    </nav>
  )
}

export type InspectorMode = "configure" | "meson" | "trace"

const INSPECTOR_TABS: { id: InspectorMode; label: string }[] = [
  { id: "configure", label: "Configure" },
  { id: "meson", label: "Meson" },
  { id: "trace", label: "Run / Trace" },
]

/** Right contextual inspector: one surface, three modes. Configure is the default. */
export function BuilderInspector({
  mode,
  onModeChange,
  mesonAttention = false,
  traceLive = false,
  children,
}: {
  mode: InspectorMode
  onModeChange: (mode: InspectorMode) => void
  mesonAttention?: boolean
  traceLive?: boolean
  children: ReactNode
}) {
  return (
    <aside
      aria-label="Inspector"
      data-review-surface="builder-inspector"
      data-inspector-mode={mode}
      className="hidden min-h-0 shrink-0 flex-col border-l border-[color:var(--g-border-subtle)] bg-card dark:border-[color:var(--graphite-700)] md:flex md:w-[300px] xl:w-[340px]"
    >
      <div role="tablist" aria-label="Inspector mode" className="flex h-10 shrink-0 items-stretch gap-4 border-b border-[color:var(--g-border-subtle)] px-4">
        {INSPECTOR_TABS.map((tab) => {
          const selected = tab.id === mode
          const showDot = (tab.id === "meson" && mesonAttention && !selected) || (tab.id === "trace" && traceLive)
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`inspector-tab-${tab.id}`}
              aria-selected={selected}
              aria-controls="builder-inspector-panel"
              onClick={() => onModeChange(tab.id)}
              className={cn(
                "relative inline-flex items-center gap-1.5 text-[13px] font-medium transition-colors",
                "after:absolute after:inset-x-0 after:-bottom-px after:h-[2px] after:content-['']",
                selected
                  ? "text-foreground after:bg-[color:var(--g-text-primary)]"
                  : "text-muted-foreground hover:text-foreground after:bg-transparent",
              )}
            >
              {tab.label}
              {showDot ? (
                <span
                  aria-hidden
                  className={cn(
                    "size-1.5 rounded-full",
                    tab.id === "trace" ? "bg-[color:var(--info)] motion-safe:animate-pulse" : "bg-[color:var(--g-brand)]",
                  )}
                />
              ) : null}
            </button>
          )
        })}
      </div>
      <div
        role="tabpanel"
        id="builder-inspector-panel"
        aria-labelledby={`inspector-tab-${mode}`}
        className="flex min-h-0 flex-1 flex-col overflow-y-auto"
      >
        {children}
      </div>
    </aside>
  )
}

export type GraphEndNode = {
  id: string
  name: string
  typeLabel: string
  icon: IconType
  configKeys: string[]
}

function InspectorSection({ title, meta, children }: { title: string; meta?: ReactNode; children: ReactNode }) {
  return (
    <section className="border-b border-[color:var(--g-border-subtle)] px-4 py-4">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="text-[13px] font-semibold text-foreground">{title}</h3>
        {meta ? <span className="font-mono text-xs text-muted-foreground">{meta}</span> : null}
      </div>
      {children}
    </section>
  )
}

function EndNodeRow({ node, onSelect, detail }: { node: GraphEndNode; onSelect: (id: string) => void; detail: ReactNode }) {
  const Icon = node.icon
  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      className="flex w-full items-start gap-2.5 rounded-[5px] px-2 py-2 text-left transition-colors hover:bg-[color:var(--g-surface-2)]"
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium text-foreground">{node.name}</span>
        <span className="block text-xs text-muted-foreground">{node.typeLabel}</span>
        <span className="mt-1 block">{detail}</span>
      </span>
    </button>
  )
}

function ConfigKeyList({ keys, empty }: { keys: string[]; empty: string }) {
  if (keys.length === 0) return <span className="text-xs text-muted-foreground">{empty}</span>
  return (
    <span className="flex flex-wrap gap-x-2 gap-y-0.5">
      {keys.slice(0, 6).map((key) => (
        <span key={key} className="font-mono text-xs text-[color:var(--g-text-secondary)]">
          {key}
        </span>
      ))}
      {keys.length > 6 ? <span className="font-mono text-xs text-muted-foreground">+{keys.length - 6}</span> : null}
    </span>
  )
}

/**
 * Configure mode with nothing selected: the workflow itself. Start and End are the
 * graph's entry and terminal steps — a reading of the existing graph, not new node types.
 */
export function BuilderWorkflowOverview({
  intent,
  entryNodes,
  terminalNodes,
  stepCount,
  blockingIssues,
  onSelectNode,
  onAddStep,
}: {
  intent: string
  entryNodes: GraphEndNode[]
  terminalNodes: GraphEndNode[]
  stepCount: number
  blockingIssues: number
  onSelectNode: (id: string) => void
  onAddStep: () => void
}) {
  const workCount = Math.max(0, stepCount - new Set([...entryNodes, ...terminalNodes].map((n) => n.id)).size)
  return (
    <div data-review-surface="builder-overview">
      <InspectorSection title="Workflow">
        <p className="text-[13px] leading-5 text-foreground">
          {intent || "Name the outcome this workflow should produce, then orchestrate it on the canvas."}
        </p>
        <p className="mt-2 text-xs text-muted-foreground">Select a step on the canvas to configure it.</p>
        {blockingIssues > 0 ? (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-[color:var(--warning)]">
            <span aria-hidden className="size-1.5 rounded-full bg-[color:var(--g-approval)]" />
            {blockingIssues} connector {blockingIssues === 1 ? "issue" : "issues"} to resolve before saving
          </p>
        ) : null}
      </InspectorSection>

      <InspectorSection title="Start · inputs" meta={entryNodes.length || undefined}>
        {entryNodes.length === 0 ? (
          <p className="text-xs text-muted-foreground">No entry step yet.</p>
        ) : (
          <div className="-mx-2 flex flex-col">
            {entryNodes.map((node) => (
              <EndNodeRow
                key={node.id}
                node={node}
                onSelect={onSelectNode}
                detail={<ConfigKeyList keys={node.configKeys} empty="No inputs configured" />}
              />
            ))}
          </div>
        )}
      </InspectorSection>

      <InspectorSection title="Work" meta={workCount}>
        <p className="text-xs text-muted-foreground">
          {workCount === 0
            ? "No intermediate steps between start and end."
            : `${workCount} ${workCount === 1 ? "step runs" : "steps run"} between start and end.`}
        </p>
        <Button variant="outline" size="sm" className="mt-3 h-8 gap-1.5" onClick={onAddStep}>
          <Plus className="h-3.5 w-3.5" />
          Add step
        </Button>
      </InspectorSection>

      <InspectorSection title="End · output" meta={terminalNodes.length || undefined}>
        {terminalNodes.length === 0 ? (
          <p className="text-xs text-muted-foreground">No terminal step yet.</p>
        ) : (
          <div className="-mx-2 flex flex-col">
            {terminalNodes.map((node) => (
              <EndNodeRow
                key={node.id}
                node={node}
                onSelect={onSelectNode}
                detail={<span className="text-xs text-muted-foreground">Workflow output is this step&apos;s result</span>}
              />
            ))}
          </div>
        )}
      </InspectorSection>
    </div>
  )
}

export type TraceStatus = "idle" | "running" | "completed" | "error" | "paused" | "cancelled" | "waiting"

const TRACE_STATUS: Record<TraceStatus, { label: string; dot: string }> = {
  idle: { label: "No active run", dot: "bg-[color:var(--g-text-muted)]" },
  running: { label: "Running", dot: "bg-[color:var(--info)] motion-safe:animate-pulse" },
  completed: { label: "Completed", dot: "bg-[color:var(--g-brand)]" },
  error: { label: "Failed", dot: "bg-destructive" },
  paused: { label: "Paused", dot: "bg-[color:var(--g-approval)]" },
  waiting: { label: "Awaiting approval", dot: "bg-[color:var(--g-approval)]" },
  cancelled: { label: "Cancelled", dot: "bg-destructive" },
}

const NODE_STATE_DOT: Record<string, { label: string; dot: string }> = {
  running: { label: "Running", dot: "bg-[color:var(--info)] motion-safe:animate-pulse" },
  evaluating: { label: "Evaluating", dot: "bg-[color:var(--info)] motion-safe:animate-pulse" },
  debating: { label: "Debating", dot: "bg-[color:var(--info)] motion-safe:animate-pulse" },
  success: { label: "Completed", dot: "bg-[color:var(--g-brand)]" },
  consensus: { label: "Consensus", dot: "bg-[color:var(--g-brand)]" },
  error: { label: "Failed", dot: "bg-destructive" },
  escalated: { label: "Escalated", dot: "bg-destructive" },
  waiting: { label: "Waiting", dot: "bg-[color:var(--g-approval)]" },
}

export type TraceNode = { id: string; name: string; typeLabel: string; state?: string; stepError?: string }

/** Run / Trace mode: reads the builder's existing execution state; the graph stays in view. */
export function BuilderRunTrace({
  status,
  step,
  total,
  elapsedSeconds,
  error,
  nodes,
  lastRunId,
  traceOverlay,
  onToggleTraceOverlay,
  onSelectNode,
}: {
  status: TraceStatus
  step: number
  total: number
  elapsedSeconds: number
  error: string | null
  nodes: TraceNode[]
  lastRunId: string | null
  traceOverlay: boolean
  onToggleTraceOverlay: () => void
  onSelectNode: (id: string) => void
}) {
  const meta = TRACE_STATUS[status]
  const active = status !== "idle"
  return (
    <div data-review-surface="builder-trace">
      <InspectorSection title="Run" meta={lastRunId ? lastRunId.slice(0, 8) : undefined}>
        <p className="inline-flex items-center gap-1.5 text-[13px] font-medium text-foreground">
          <span aria-hidden className={cn("size-1.5 rounded-full", meta.dot)} />
          {meta.label}
        </p>
        {active ? (
          <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Step</dt>
            <dd className="font-mono text-foreground">
              {Math.min(step, total)} / {total}
            </dd>
            <dt className="text-muted-foreground">Elapsed</dt>
            <dd className="font-mono text-foreground">{elapsedSeconds}s</dd>
          </dl>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">Run the workflow to watch each step on the canvas.</p>
        )}
        {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant={traceOverlay ? "secondary" : "outline"}
            size="sm"
            className="h-8 gap-1.5"
            aria-pressed={traceOverlay}
            onClick={onToggleTraceOverlay}
          >
            <Activity className="h-3.5 w-3.5" />
            Trace overlay
          </Button>
          {lastRunId ? (
            <Button asChild variant="ghost" size="sm" className="h-8 gap-1.5">
              <Link href={`/runs/${lastRunId}`}>
                <ExternalLink className="h-3.5 w-3.5" />
                Open run
              </Link>
            </Button>
          ) : null}
        </div>
      </InspectorSection>

      <InspectorSection title="Steps" meta={nodes.length}>
        <ol className="-mx-2 flex flex-col">
          {nodes.map((node) => {
            const state = node.state && node.state !== "idle" ? NODE_STATE_DOT[node.state] : undefined
            return (
              <li key={node.id}>
                <button
                  type="button"
                  onClick={() => onSelectNode(node.id)}
                  className="flex w-full items-start gap-2.5 rounded-[5px] px-2 py-1.5 text-left transition-colors hover:bg-[color:var(--g-surface-2)]"
                >
                  <span
                    aria-hidden
                    className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", state?.dot ?? "bg-[color:var(--g-border-strong)]")}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] text-foreground">{node.name}</span>
                    <span className="block text-xs text-muted-foreground">
                      {node.typeLabel} · {state?.label ?? (active ? "Not reached" : "Not run")}
                    </span>
                    {node.stepError ? (
                      <span className="mt-0.5 block text-xs text-destructive">{node.stepError}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      </InspectorSection>
    </div>
  )
}
