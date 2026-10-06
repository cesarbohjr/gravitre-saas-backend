"use client"

import type { ComponentType, CSSProperties, ReactNode } from "react"
import Link from "next/link"
import {
  Activity,
  Bot,
  Database,
  ExternalLink,
  GitBranch,
  Maximize2,
  PanelRight,
  Plug,
  Plus,
  Sparkles,
  Wrench,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

type IconType = ComponentType<{ className?: string; style?: CSSProperties }>

export type CanvasLibraryTab = "agents" | "connectors" | "sources" | "tools" | "decisions"

/** Step categories, colour-coded the same way on the canvas, the rail legend and the library. */
export const NODE_CATEGORY_ACCENTS = {
  ai: { label: "AI agents", color: "var(--g-intelligence)" },
  apps: { label: "Apps & data", color: "var(--g-emerald)" },
  logic: { label: "Logic", color: "#8b6cf0" },
  approval: { label: "Approvals", color: "var(--g-approval)" },
} as const

export type NodeCategory = keyof typeof NODE_CATEGORY_ACCENTS

export function nodeCategory(type: string): NodeCategory {
  if (type === "agent" || type === "council") return "ai"
  if (type === "approval") return "approval"
  if (type === "decision" || type === "if" || type === "switch" || type === "merge" || type === "loop") return "logic"
  return "apps"
}

type RailTool = {
  key: string
  label: string
  icon: IconType
  onClick: () => void
  pressed?: boolean
  accent?: string
}

function RailButton({ tool }: { tool: RailTool }) {
  const Icon = tool.icon
  return (
    <button
      type="button"
      onClick={tool.onClick}
      title={tool.label}
      aria-pressed={tool.pressed}
      className={cn(
        "relative flex h-8 w-full items-center gap-2.5 rounded-[5px] px-2 text-[13px] font-medium transition-colors",
        "justify-center xl:justify-start",
        tool.pressed
          ? "bg-[color:var(--g-emerald-pale)] text-[color:var(--g-text-primary)] before:absolute before:inset-y-1.5 before:left-0 before:w-[2px] before:rounded-full before:bg-[color:var(--g-emerald)] before:content-['']"
          : "text-muted-foreground hover:bg-[color:var(--g-chrome-hover)] hover:text-foreground",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" style={tool.accent ? { color: tool.accent } : undefined} />
      <span className="sr-only xl:not-sr-only xl:truncate">{tool.label}</span>
    </button>
  )
}

/**
 * Canvas tool rail: adding steps by category and canvas view controls. Site navigation
 * lives in the app sidebar; this rail only acts on the canvas.
 */
export function BuilderCanvasRail({
  onAddStep,
  onFitView,
  onShowOverview,
  overviewOpen = false,
  traceOverlay = false,
  onToggleTraceOverlay,
  mesonOpen = false,
  onToggleMeson,
}: {
  onAddStep: (tab?: CanvasLibraryTab) => void
  onFitView: () => void
  onShowOverview: () => void
  overviewOpen?: boolean
  traceOverlay?: boolean
  onToggleTraceOverlay: () => void
  mesonOpen?: boolean
  onToggleMeson: () => void
}) {
  const groups: { label: string; tools: RailTool[] }[] = [
    {
      label: "Add to canvas",
      tools: [
        { key: "add", label: "Add step", icon: Plus, onClick: () => onAddStep() },
        { key: "agents", label: "Agents", icon: Bot, onClick: () => onAddStep("agents"), accent: NODE_CATEGORY_ACCENTS.ai.color },
        { key: "connectors", label: "Apps", icon: Plug, onClick: () => onAddStep("connectors"), accent: NODE_CATEGORY_ACCENTS.apps.color },
        { key: "sources", label: "Sources", icon: Database, onClick: () => onAddStep("sources"), accent: NODE_CATEGORY_ACCENTS.apps.color },
        { key: "tools", label: "Tools", icon: Wrench, onClick: () => onAddStep("tools"), accent: NODE_CATEGORY_ACCENTS.apps.color },
        { key: "decisions", label: "Logic & approvals", icon: GitBranch, onClick: () => onAddStep("decisions"), accent: NODE_CATEGORY_ACCENTS.logic.color },
      ],
    },
    {
      label: "Canvas",
      tools: [
        { key: "fit", label: "Fit workflow", icon: Maximize2, onClick: onFitView },
        { key: "overview", label: "Workflow details", icon: PanelRight, onClick: onShowOverview, pressed: overviewOpen },
        { key: "trace", label: "Trace overlay", icon: Activity, onClick: onToggleTraceOverlay, pressed: traceOverlay },
        { key: "meson", label: "Meson", icon: Sparkles, onClick: onToggleMeson, pressed: mesonOpen },
      ],
    },
  ]

  return (
    <nav
      aria-label="Canvas tools"
      data-review-surface="builder-canvas-rail"
      data-composition="create"
      className="hidden shrink-0 flex-col gap-4 overflow-y-auto border-r border-[color:var(--g-border-subtle)] bg-[color:var(--g-chrome)] py-3 lg:flex lg:w-12 xl:w-48"
    >
      {groups.map((group) => (
        <div key={group.label} className="flex flex-col gap-0.5 px-1.5 xl:px-2">
          <p className="hidden px-2 pb-1 text-xs font-medium text-muted-foreground xl:block">{group.label}</p>
          {group.tools.map((tool) => (
            <RailButton key={tool.key} tool={tool} />
          ))}
        </div>
      ))}
      <div className="mt-auto hidden flex-col gap-1.5 px-4 pb-1 xl:flex" aria-label="Step colours">
        <p className="pb-0.5 text-xs font-medium text-muted-foreground">Step colours</p>
        {Object.values(NODE_CATEGORY_ACCENTS).map((accent) => (
          <span key={accent.label} className="flex items-center gap-2 text-xs text-muted-foreground">
            <span aria-hidden className="size-2 rounded-full" style={{ background: accent.color }} />
            {accent.label}
          </span>
        ))}
      </div>
      <p className="mt-auto px-2 text-center text-[10px] leading-3 text-muted-foreground xl:hidden" title="Drag empty canvas to pan">
        Drag to pan
      </p>
      <p className="hidden px-4 text-[11px] text-muted-foreground xl:block">Drag empty canvas to pan.</p>
    </nav>
  )
}

export type InspectorMode = "configure" | "meson" | "trace"

const INSPECTOR_TABS: { id: InspectorMode; label: string }[] = [
  { id: "configure", label: "Configure" },
  { id: "meson", label: "Meson" },
  { id: "trace", label: "Run / Trace" },
]

/**
 * Right contextual inspector: one surface, three modes. Configure is the default.
 * The builder opens it when something on the canvas is selected; `onClose` adds the X.
 */
export function BuilderInspector({
  mode,
  onModeChange,
  mesonAttention = false,
  traceLive = false,
  onClose,
  children,
}: {
  mode: InspectorMode
  onModeChange: (mode: InspectorMode) => void
  mesonAttention?: boolean
  traceLive?: boolean
  onClose?: () => void
  children: ReactNode
}) {
  return (
    <aside
      aria-label="Inspector"
      data-review-surface="builder-inspector"
      data-inspector-mode={mode}
      className="dark hidden min-h-0 shrink-0 flex-col border-l animate-in slide-in-from-right-2 duration-200 border-[color:var(--g-border-subtle)] bg-[color:var(--g-carbon)] text-foreground lg:flex lg:w-[300px] xl:w-[340px]"
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
                  ? "text-foreground after:bg-[color:var(--g-emerald)]"
                  : "text-muted-foreground hover:text-foreground after:bg-transparent",
              )}
            >
              {tab.label}
              {showDot ? (
                <span
                  aria-hidden
                  className={cn(
                    "size-1.5 rounded-full",
                    tab.id === "trace" ? "bg-[color:var(--g-electric)]" : "bg-[color:var(--g-emerald)]",
                  )}
                />
              ) : null}
            </button>
          )
        })}
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            title="Close panel (Esc)"
            className="ml-auto inline-flex h-7 w-7 items-center justify-center self-center rounded-[5px] text-muted-foreground transition-colors hover:bg-[color:var(--g-surface-2)] hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
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
  completed: { label: "Verified", dot: "bg-[color:var(--g-emerald)]" },
  error: { label: "Failed", dot: "bg-destructive" },
  paused: { label: "Paused", dot: "bg-[color:var(--g-approval)]" },
  waiting: { label: "Awaiting approval", dot: "bg-[color:var(--g-approval)]" },
  cancelled: { label: "Cancelled", dot: "bg-destructive" },
}

const NODE_STATE_DOT: Record<string, { label: string; dot: string }> = {
  running: { label: "Running", dot: "bg-[color:var(--info)] motion-safe:animate-pulse" },
  evaluating: { label: "Evaluating", dot: "bg-[color:var(--info)] motion-safe:animate-pulse" },
  debating: { label: "Debating", dot: "bg-[color:var(--info)] motion-safe:animate-pulse" },
  success: { label: "Verified", dot: "bg-[color:var(--g-emerald)]" },
  consensus: { label: "Consensus", dot: "bg-[color:var(--g-emerald)]" },
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
