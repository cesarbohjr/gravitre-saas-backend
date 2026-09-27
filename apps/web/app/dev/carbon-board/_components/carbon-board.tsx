"use client"

/**
 * Carbon Intelligence design board — the visual regression reference for 3.0 Plus.
 * Internal only (noindex, /dev). Everything interactive is a production primitive;
 * sample rows, names and values are labelled placeholders, never product claims.
 */
import { useState, type ReactNode } from "react"
import { Bot, Check, FileText, GitBranch, Play, Plug, Save, Search, Settings, ShieldCheck, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import { HUB_TABS, TYPE } from "@/lib/design-system"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { BuilderInspector, BuilderRunTrace, type InspectorMode } from "@/components/workflows/builder-chrome"

const SWATCHES: { group: string; items: { name: string; hex: string; role: string }[] }[] = [
  {
    group: "Carbon (dark surfaces)",
    items: [
      { name: "Carbon 950", hex: "#0A0B0C", role: "Dark canvas, frame" },
      { name: "Carbon 900", hex: "#111315", role: "Dark card" },
      { name: "Graphite 800", hex: "#1A1D20", role: "Dark popover, raised" },
      { name: "Graphite 700", hex: "#25292D", role: "Dark accent, hover" },
    ],
  },
  {
    group: "Porcelain (light surfaces)",
    items: [
      { name: "Porcelain 50", hex: "#F7F7F5", role: "Light canvas" },
      { name: "Bone 100", hex: "#EFEFEB", role: "Chrome, secondary" },
      { name: "Ink 950", hex: "#151618", role: "Text, primary action" },
      { name: "Muted", hex: "#6F767E", role: "Icons, meta (dark: #B7BDC4)" },
    ],
  },
  {
    group: "Signal (live, healthy, verified, selected)",
    items: [
      { name: "Signal 500", hex: "#2FBF8F", role: "Dot, edge, selection" },
      { name: "Signal 600", hex: "#239B75", role: "Hover" },
      { name: "Signal 300", hex: "#79D8B8", role: "Dark-mode active" },
      { name: "Signal wash", hex: "#E8F5EF", role: "Subtle selected wash" },
    ],
  },
  {
    group: "Ion (intelligence, evidence, reasoning)",
    items: [
      { name: "Ion 500", hex: "#7C6CF2", role: "Graph journey, evidence" },
      { name: "Ion 300", hex: "#A89CF8", role: "Dark-mode ion" },
      { name: "Ion wash", hex: "#F0EEFF", role: "Evidence wash" },
    ],
  },
  {
    group: "Semantic (edge, dot, icon, text only)",
    items: [
      { name: "Attention", hex: "#C8902F", role: "Approval, pending" },
      { name: "Failure", hex: "#C94C4C", role: "Failed, destructive" },
      { name: "Information", hex: "#4E7FCB", role: "Running, info" },
    ],
  },
]

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="border-t border-[color:var(--g-border-subtle)] py-6">
      <div className="mb-4">
        <h2 className={TYPE.sectionTitle}>{title}</h2>
        {note ? <p className={cn(TYPE.meta, "mt-0.5")}>{note}</p> : null}
      </div>
      {children}
    </section>
  )
}

function Swatches() {
  return (
    <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
      {SWATCHES.map((group) => (
        <div key={group.group}>
          <p className="mb-2 text-[13px] font-medium text-foreground">{group.group}</p>
          <ul className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-subtle)]">
            {group.items.map((s) => (
              <li key={s.name} className="flex items-center gap-3 py-2">
                <span
                  aria-hidden
                  className="h-7 w-7 shrink-0 rounded-[5px] border border-[color:var(--g-border-default)]"
                  style={{ background: s.hex }}
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-foreground">{s.name}</span>
                  <span className="block text-xs text-muted-foreground">{s.role}</span>
                </span>
                <span className={TYPE.mono}>{s.hex}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function TypeScale() {
  const rows: { label: string; spec: string; node: ReactNode }[] = [
    { label: "Page", spec: "28 / 600", node: <p className={TYPE.pageTitle}>Workflows</p> },
    { label: "Workspace", spec: "20 / 600", node: <p className={TYPE.workspaceTitle}>Customer data pipeline</p> },
    { label: "Section", spec: "15 / 600", node: <p className={TYPE.sectionTitle}>Recent runs</p> },
    { label: "Body", spec: "14 / 400", node: <p className={TYPE.body}>Configuration lives in the inspector, not behind Ask.</p> },
    { label: "Meta", spec: "12 / 400", node: <p className={TYPE.meta}>Updated 4 minutes ago</p> },
    { label: "Mono", spec: "12 / 500", node: <p className={TYPE.mono}>wf_3f9a2c · v1.2.0 · 2026-09-27T12:00Z</p> },
  ]
  return (
    <dl className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-subtle)]">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[96px_80px_1fr] items-baseline gap-4 py-3">
          <dt className="text-[13px] font-medium text-foreground">{r.label}</dt>
          <dd className={TYPE.mono}>{r.spec}</dd>
          <dd className="min-w-0">{r.node}</dd>
        </div>
      ))}
    </dl>
  )
}

function IconRules() {
  const icons = [Bot, Plug, GitBranch, ShieldCheck, FileText, Search, Settings, Sparkles]
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <p className="mb-2 text-[13px] font-medium text-foreground">Do: monochrome line, 16–18px, no frame</p>
        <div className="flex flex-wrap items-center gap-4 text-foreground">
          {icons.map((I, i) => (
            <I key={i} className="h-4 w-4" />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-muted-foreground">
          {icons.map((I, i) => (
            <I key={i} className="h-[18px] w-[18px]" />
          ))}
        </div>
      </div>
      <div>
        <p className="mb-2 text-[13px] font-medium text-foreground">Don&apos;t: colored tiles, gradients, glow</p>
        <p className="text-xs text-muted-foreground">
          Node types and capabilities are told apart by icon and label. Connector logos are the only brand-colored
          marks. A neutral frame is allowed on canvas nodes, never a tinted one.
        </p>
      </div>
    </div>
  )
}

function Controls() {
  const [tab, setTab] = useState("overview")
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <div className="space-y-3">
        <p className="text-[13px] font-medium text-foreground">Buttons</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button>
            <Play className="h-3.5 w-3.5" />
            Primary
          </Button>
          <Button variant="outline">
            <Save className="h-3.5 w-3.5" />
            Secondary
          </Button>
          <Button variant="ghost">Tertiary</Button>
          <Button variant="destructive">Destructive</Button>
          <Button disabled>Disabled</Button>
        </div>
        <p className="text-xs text-muted-foreground">Primary is ink, not green. Radius 5px. No pills.</p>
      </div>
      <div className="space-y-3">
        <p className="text-[13px] font-medium text-foreground">Tabs (underline)</p>
        <nav className={HUB_TABS.nav} aria-label="Sample tabs">
          {["overview", "runs", "settings"].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(HUB_TABS.link, "capitalize", tab === t ? HUB_TABS.active : HUB_TABS.idle)}
            >
              {t}
            </button>
          ))}
        </nav>
      </div>
      <div className="space-y-3">
        <p className="text-[13px] font-medium text-foreground">Status: dot + label</p>
        <div className="flex flex-wrap items-center gap-4">
          <StatusBadge tone="verified">Verified</StatusBadge>
          <StatusBadge tone="running">Running</StatusBadge>
          <StatusBadge tone="pending">Awaiting approval</StatusBadge>
          <StatusBadge tone="failed">Failed</StatusBadge>
          <StatusBadge tone="idle">Idle</StatusBadge>
          <EnvironmentBadge environment="production" />
          <EnvironmentBadge environment="staging" />
        </div>
      </div>
      <div className="space-y-3">
        <p className="text-[13px] font-medium text-foreground">Badges</p>
        <div className="flex flex-wrap items-center gap-3">
          <Badge>Category</Badge>
          <Badge variant="outline">12</Badge>
          <Badge variant="status">Live</Badge>
          <Badge variant="warning">Needs approval</Badge>
          <Badge variant="destructive">Blocked</Badge>
        </div>
      </div>
    </div>
  )
}

function SampleTable() {
  const rows = [
    { name: "Placeholder workflow A", env: "production" as const, tone: "verified" as const, label: "Healthy", id: "wf_0001" },
    { name: "Placeholder workflow B", env: "staging" as const, tone: "pending" as const, label: "Awaiting approval", id: "wf_0002" },
    { name: "Placeholder workflow C", env: "staging" as const, tone: "failed" as const, label: "Failed", id: "wf_0003" },
  ]
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left">
        <thead>
          <tr className="border-b border-[color:var(--g-border-default)]">
            {["Workflow", "Environment", "Status", "ID"].map((h) => (
              <th key={h} className={cn(TYPE.tableHead, "py-2 pr-4 font-medium")}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.id}
              className={cn(
                "border-b border-[color:var(--g-border-subtle)]",
                i === 0 && "bg-[color:var(--g-brand-soft)] shadow-[inset_2px_0_0_var(--g-brand)]",
              )}
            >
              <td className="py-2.5 pr-4 text-[13px] font-medium text-foreground">{r.name}</td>
              <td className="py-2.5 pr-4">
                <EnvironmentBadge environment={r.env} />
              </td>
              <td className="py-2.5 pr-4">
                <StatusBadge tone={r.tone}>{r.label}</StatusBadge>
              </td>
              <td className={cn(TYPE.mono, "py-2.5 pr-4")}>{r.id}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted-foreground">First row shows the selected state: signal edge + wash.</p>
    </div>
  )
}

function SampleNode({
  icon: Icon,
  name,
  type,
  selected,
  state,
}: {
  icon: typeof Bot
  name: string
  type: string
  selected?: boolean
  state?: { label: string; dot: string }
}) {
  return (
    <div
      className={cn(
        "relative w-56 rounded-[var(--np-radius-lg)] border bg-card p-3",
        selected
          ? "border-[color:var(--g-brand)] ring-2 ring-[color:var(--g-brand)]/15"
          : "border-[color:var(--g-border-default)]",
      )}
    >
      {state ? (
        <span className="absolute -top-2.5 left-3 inline-flex items-center gap-1.5 rounded-[4px] border border-[color:var(--g-border-default)] bg-card px-1.5 py-0.5 text-[11px] font-medium text-foreground">
          <span aria-hidden className={cn("size-1.5 rounded-full", state.dot)} />
          {state.label}
        </span>
      ) : null}
      <div className="flex items-start gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-2)] text-foreground">
          <Icon className="h-4 w-4" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-foreground">{name}</span>
          <span className="block text-[11px] text-muted-foreground">{type}</span>
        </span>
      </div>
    </div>
  )
}

function Nodes() {
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <div>
        <p className="mb-3 text-[13px] font-medium text-foreground">Workflow nodes</p>
        <div
          className="flex flex-wrap gap-x-6 gap-y-8 rounded-[8px] border border-[color:var(--g-border-subtle)] p-6"
          style={{ backgroundImage: "radial-gradient(circle, var(--g-border-strong) 1px, transparent 1px)", backgroundSize: "20px 20px" }}
        >
          <SampleNode icon={Bot} name="Placeholder agent" type="Agent" selected />
          <SampleNode icon={Plug} name="Placeholder connector" type="Connector" state={{ label: "Running", dot: "bg-[color:var(--info)]" }} />
          <SampleNode icon={ShieldCheck} name="Placeholder approval" type="Approval" state={{ label: "Waiting", dot: "bg-[color:var(--g-approval)]" }} />
          <SampleNode icon={FileText} name="Placeholder output" type="Task" state={{ label: "Success", dot: "bg-[color:var(--g-brand)]" }} />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Replica of the builder&apos;s node classes (the canvas node is private to the builder route).
        </p>
      </div>
      <div>
        <p className="mb-3 text-[13px] font-medium text-foreground">Graph node (intelligence)</p>
        <div className="flex flex-wrap items-center gap-6 rounded-[8px] border border-[color:var(--g-border-subtle)] p-6">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--g-intelligence)]" />
            <span className="text-[13px] text-foreground">Placeholder entity</span>
          </div>
          <span className="h-px w-16 bg-[color:var(--g-intelligence)]/50" />
          <div className="rounded-[6px] border border-[color:var(--g-intelligence)]/40 bg-[color:var(--g-intelligence-soft)] px-2.5 py-1.5">
            <span className="block text-[13px] font-medium text-foreground">Evidence</span>
            <span className={TYPE.mono}>src_0142</span>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Ion marks relationships and evidence only; it is never a second brand color.</p>
      </div>
    </div>
  )
}

function States() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="rounded-[8px] border border-[color:var(--g-border-default)] bg-[color:var(--g-brand-soft)] p-4 shadow-[inset_2px_0_0_var(--g-brand)]">
        <p className="text-[13px] font-medium text-foreground">Selected</p>
        <p className="mt-1 text-xs text-muted-foreground">Signal edge + wash. Used for AI selection and the active operational row.</p>
      </div>
      <div className="rounded-[8px] border border-[color:var(--g-border-default)] bg-card p-4 shadow-[inset_2px_0_0_var(--g-approval)]">
        <p className="inline-flex items-center gap-1.5 text-[13px] font-medium text-foreground">
          <span aria-hidden className="size-1.5 rounded-full bg-[color:var(--g-approval)]" />
          Approval required
        </p>
        <p className="mt-1 text-xs text-muted-foreground">Attention edge, no amber card fill.</p>
        <div className="mt-3 flex gap-2">
          <Button size="sm">
            <Check className="h-3.5 w-3.5" />
            Approve
          </Button>
          <Button size="sm" variant="outline">
            Reject
          </Button>
        </div>
      </div>
      <div className="rounded-[8px] border border-[color:var(--g-border-default)] bg-card p-4">
        <p className="text-[13px] font-medium text-foreground">Artifact</p>
        <p className={cn(TYPE.mono, "mt-1")}>artifact_placeholder.csv · 12 KB</p>
        <p className="mt-1 text-xs text-muted-foreground">Flat row, mono metadata, no tile.</p>
      </div>
    </div>
  )
}

function Dock() {
  return (
    <div className="flex flex-wrap items-center gap-6">
      <div className="inline-flex h-11 items-center gap-2 rounded-[8px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] pl-1 pr-3 shadow-[0_8px_20px_-12px_rgb(0_0_0/0.4)]">
        <span className="flex h-8 w-8 items-center justify-center text-foreground">
          <Sparkles className="h-4 w-4" />
        </span>
        <span className="text-[13px] font-medium text-foreground">Ask Gravitre</span>
        <span className="text-xs text-muted-foreground">· Workflows</span>
        <span className="ml-1 inline-flex items-center gap-1.5 text-xs font-medium text-foreground">
          <span aria-hidden className="size-1.5 rounded-full bg-[color:var(--g-approval)]" />2
        </span>
      </div>
      <p className="max-w-sm text-xs text-muted-foreground">
        Replica of the AI dock treatment: graphite surface, restrained dot, context label, no bright tile.
      </p>
    </div>
  )
}

function Inspector() {
  const [mode, setMode] = useState<InspectorMode>("trace")
  return (
    <div className="flex h-[420px] overflow-hidden rounded-[8px] border border-[color:var(--g-border-default)]">
      <div className="flex-1 bg-background" />
      <div className="flex [&>aside]:flex">
        <BuilderInspector mode={mode} onModeChange={setMode} traceLive>
          {mode === "trace" ? (
            <BuilderRunTrace
              status="running"
              step={2}
              total={4}
              elapsedSeconds={14}
              error={null}
              lastRunId={null}
              traceOverlay
              onToggleTraceOverlay={() => {}}
              onSelectNode={() => {}}
              nodes={[
                { id: "a", name: "Placeholder source", typeLabel: "Source", state: "success" },
                { id: "b", name: "Placeholder agent", typeLabel: "Agent", state: "running" },
                { id: "c", name: "Placeholder approval", typeLabel: "Approval" },
                { id: "d", name: "Placeholder connector", typeLabel: "Connector", state: "error", stepError: "Placeholder error text" },
              ]}
            />
          ) : (
            <p className="px-4 py-4 text-xs text-muted-foreground">
              {mode === "configure" ? "Configure mode renders the node's configuration panel." : "Meson mode renders the Meson copilot."}
            </p>
          )}
        </BuilderInspector>
      </div>
    </div>
  )
}

function Board() {
  return (
    <div className="mx-auto max-w-6xl px-6 pb-16">
      <Section title="Palette">
        <Swatches />
      </Section>
      <Section title="Typography" note="Inter Display + DM Mono (Geist not installed; existing stack kept per fallback rule).">
        <TypeScale />
      </Section>
      <Section title="Icons">
        <IconRules />
      </Section>
      <Section title="Controls and status">
        <Controls />
      </Section>
      <Section title="Table">
        <SampleTable />
      </Section>
      <Section title="Workflow and graph nodes">
        <Nodes />
      </Section>
      <Section title="Selected, approval, artifact">
        <States />
      </Section>
      <Section title="AI dock">
        <Dock />
      </Section>
      <Section title="Inspector (production component)">
        <Inspector />
      </Section>
    </div>
  )
}

export function CarbonBoard() {
  const [theme, setTheme] = useState<"light" | "dark">("light")
  return (
    <div data-page-family="expert" className={cn("min-h-screen bg-background text-foreground", theme === "dark" && "dark")}>
      <header className="border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-chrome)]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-5">
          <div>
            <p className="inline-flex items-center gap-1.5 text-xs font-medium text-[color:var(--warning)]">
              <span aria-hidden className="size-1.5 rounded-full bg-[color:var(--g-approval)]" />
              Internal design board · placeholder content · not a product surface
            </p>
            <h1 className={cn(TYPE.pageTitle, "mt-1")}>Gravitre Carbon Intelligence</h1>
            <p className={TYPE.pageLead}>Regression reference for tokens and shared primitives.</p>
          </div>
          <nav className={HUB_TABS.nav} aria-label="Board theme">
            {(["light", "dark"] as const).map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={theme === t}
                onClick={() => setTheme(t)}
                className={cn(HUB_TABS.link, "capitalize", theme === t ? HUB_TABS.active : HUB_TABS.idle)}
              >
                {t}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <Board />
    </div>
  )
}
