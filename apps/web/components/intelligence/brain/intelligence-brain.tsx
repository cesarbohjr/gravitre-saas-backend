"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useReducedMotion } from "framer-motion"
import { Pause, Play } from "lucide-react"
import { toast } from "sonner"
import { connectorsApi, type IntelligencePageContextResponse, type PromotionCandidate } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import type { Connector } from "@/types/api"
import type { GravitreAISelectedEntity } from "@/components/gravitre/ai-workspace-provider"
import {
  buildLiveFlowModel,
  edgeKey,
  shortDate,
  type FlowEvent,
  type FlowLayerId,
  type FlowModel,
  type OutcomeAttribution,
} from "@/components/intelligence/overview/flow-model"
import { buildExampleFlowModel, EXAMPLE_START } from "@/components/intelligence/overview/example-flow"
import { useFlowPlayback } from "@/components/intelligence/overview/use-flow-playback"
import { FlowMap, TONE_VAR, placeNodes, type PlacedNode } from "@/components/intelligence/overview/flow-map"
import { FlowInspector, type InspectorSelection } from "@/components/intelligence/overview/flow-inspector"
import { LearningCards } from "@/components/intelligence/overview/learning-cards"
import { cn } from "@/lib/utils"

const SPEEDS = [0.5, 1, 2]
const panel = "rounded-[var(--np-radius-md)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]"
const segment = "flex rounded-[10px] bg-[color:var(--g-surface-2)] p-[3px]"
const segmentButton =
  "min-h-9 rounded-[8px] px-3 text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"

const NODE_KIND: Record<FlowLayerId, string> = {
  sources: "source",
  knowledge: "entity",
  learning: "learning",
  models: "model",
  forecasts: "prediction",
}

function formatCount(value: number | null): string {
  return value == null ? "—" : value.toLocaleString("en-US")
}

function StatCard({
  label,
  value,
  sub,
  valueClass,
  children,
}: {
  label: string
  value: string
  sub?: string
  valueClass?: string
  children?: React.ReactNode
}) {
  return (
    <div className={cn(panel, "flex min-w-0 flex-col gap-1.5 px-[18px] py-4")}>
      <span className="text-[13px] text-[color:var(--g-text-secondary)]">{label}</span>
      <span className={cn("truncate text-[22px] font-semibold leading-tight sm:text-[28px] tracking-[-0.02em] tabular-nums text-foreground", valueClass)}>
        {value}
      </span>
      {sub ? <span className="text-xs text-[color:var(--g-text-muted)]">{sub}</span> : null}
      {children}
    </div>
  )
}

/** Nodes upstream and downstream of `id` along recorded links, plus its direct neighbours. */
function lineage(model: FlowModel, id: string): { nodes: Set<string>; edges: Set<string> } {
  const evidence = model.edges.filter((e) => e.evidence)
  const nodes = new Set<string>([id])
  const walk = (dir: "up" | "down") => {
    const stack = [id]
    const seen = new Set<string>()
    while (stack.length) {
      const cur = stack.pop()!
      if (seen.has(cur)) continue
      seen.add(cur)
      for (const e of evidence) {
        const next = dir === "down" ? (e.a === cur ? e.b : null) : e.b === cur ? e.a : null
        if (next) {
          nodes.add(next)
          stack.push(next)
        }
      }
    }
  }
  walk("up")
  walk("down")
  const edges = new Set<string>()
  for (const e of model.edges) {
    if (e.a === id || e.b === id) {
      nodes.add(e.a)
      nodes.add(e.b)
      edges.add(e.key)
    } else if (e.evidence && nodes.has(e.a) && nodes.has(e.b)) {
      edges.add(e.key)
    }
  }
  return { nodes, edges }
}

/**
 * Intelligence overview: the core status bar, four headline numbers, the
 * "connecting the dots" flow map with its live activity, and what Gravitre is
 * learning. Live data by default; example data only when picked, always badged.
 */
export function IntelligenceBrain({
  pageContext,
  connectors,
  candidates,
  attribution,
  avgConfidence,
  loading,
  onSelectionChange,
  onResynced,
  className,
}: {
  pageContext?: IntelligencePageContextResponse | null
  connectors?: Connector[] | null
  candidates?: PromotionCandidate[] | null
  attribution?: OutcomeAttribution
  avgConfidence?: number | null
  loading?: boolean
  onSelectionChange?: (entity: GravitreAISelectedEntity | null) => void
  onResynced?: () => void
  className?: string
}) {
  const prefersReduced = useReducedMotion() ?? false
  const [mode, setMode] = useState<"live" | "example">("live")
  const [paused, setPaused] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [selection, setSelection] = useState<InspectorSelection>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [trace, setTrace] = useState<FlowEvent | null>(null)
  const [resyncing, setResyncing] = useState(false)
  const mapRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (prefersReduced) setPaused(true)
  }, [prefersReduced])

  const liveModel = useMemo(
    () => buildLiveFlowModel({ pageContext, connectors, candidates, attribution, avgConfidence, loading }),
    [pageContext, connectors, candidates, attribution, avgConfidence, loading],
  )
  const exampleModel = useMemo(() => buildExampleFlowModel(), [])
  const example = mode === "example"
  const model = example ? exampleModel : liveModel
  const placed = useMemo(() => placeNodes(model), [model])
  const playback = useFlowPlayback(model, { paused, speed })

  const switchMode = (next: "live" | "example") => {
    setMode(next)
    setSelection(null)
    setTrace(null)
    setHover(null)
  }

  const selectedNodeId = selection?.kind === "node" ? selection.id : null
  const selectedLayer = selection?.kind === "layer" ? selection.id : null

  useEffect(() => {
    if (!onSelectionChange) return
    const node = !example && selectedNodeId ? placed.get(selectedNodeId) : null
    onSelectionChange(node && !node.placeholder ? { kind: NODE_KIND[node.layer], id: node.id, label: node.label } : null)
  }, [example, selectedNodeId, placed, onSelectionChange])

  const highlight = useMemo(() => {
    if (trace) {
      const nodes = new Set(trace.path)
      const edges = new Set<string>()
      trace.path.forEach((id, i) => {
        if (i === 0) return
        edges.add(edgeKey(trace.path[i - 1], id))
        edges.add(edgeKey(id, trace.path[i - 1]))
      })
      return { nodes, edges }
    }
    const focus = hover ?? selectedNodeId
    if (focus) return lineage(model, focus)
    if (selectedLayer) {
      const nodes = new Set<string>()
      const edges = new Set<string>()
      for (const n of model.nodes) if (n.layer === selectedLayer) nodes.add(n.id)
      for (const e of model.edges) {
        const a = placed.get(e.a)
        const b = placed.get(e.b)
        if (a?.layer === selectedLayer || b?.layer === selectedLayer) {
          edges.add(e.key)
          nodes.add(e.a)
          nodes.add(e.b)
        }
      }
      return { nodes, edges }
    }
    return null
  }, [trace, hover, selectedNodeId, selectedLayer, model, placed])

  const nodeSignals = useCallback(
    (id: string) => (example ? (playback.exampleNodeSignals[id] ?? 0) : (placed.get(id)?.signals ?? null)),
    [example, playback.exampleNodeSignals, placed],
  )
  const nodeStrength = (id: string) => {
    const ws = model.edges
      .filter((e) => (e.a === id || e.b === id) && e.evidence)
      .map((e) => e.weight + (playback.boost[e.key] ?? 0))
    return ws.length ? Math.min(1, ws.reduce((a, b) => a + b, 0) / ws.length / 6) : null
  }
  const nodeSub = (n: PlacedNode) => {
    if (!example) return n.sub
    if (n.layer === "forecasts") return playback.exampleOutcomes >= EXAMPLE_START.target ? "scored" : "not scored"
    return `${nodeSignals(n.id) ?? 0} signals`
  }

  const selectNode = (id: string) => {
    setSelection({ kind: "node", id })
    setTrace(null)
    setHover(null)
  }

  const traceLearning = (nodeId: string) => {
    selectNode(nodeId)
    mapRef.current?.scrollIntoView({ behavior: prefersReduced ? "auto" : "smooth", block: "start" })
  }

  const resync = async () => {
    const ids = liveModel.quiet?.resyncIds ?? []
    if (!ids.length) return
    setResyncing(true)
    const results = await Promise.allSettled(ids.map((id) => connectorsApi.sync(id)))
    setResyncing(false)
    const failed = results.filter((r) => r.status === "rejected").length
    if (failed === 0) toast.success(ids.length === 1 ? "Resync started" : `Resync started for ${ids.length} sources`)
    else if (failed < ids.length) toast.warning(`Resync started for ${ids.length - failed} of ${ids.length} sources`)
    else toast.error("Could not start a resync. Check the source on Connections.")
    onResynced?.()
  }

  // Header bar.
  const inFlight = playback.inFlight
  const quiet = !example ? liveModel.quiet : null
  const chip = paused ? { label: "Paused", tone: "neutral" as const } : model.coreState
  const note = example
    ? `example data · ${inFlight} ${inFlight === 1 ? "signal" : "signals"} in flight`
    : quiet
      ? liveModel.lastSignalAt
        ? `last signal ${shortDate(liveModel.lastSignalAt)}`
        : "no signal yet"
      : `live data · ${inFlight} ${inFlight === 1 ? "signal" : "signals"} in flight`

  // Stats.
  const stats = model.stats
  const fed = example ? playback.exampleOutcomes : stats.outcomesFed
  const target = stats.outcomesTarget
  const unlocked = example && playback.exampleOutcomes >= EXAMPLE_START.target
  const confPct = Math.round(40 + ((playback.exampleOutcomes - EXAMPLE_START.outcomes) / (EXAMPLE_START.target - EXAMPLE_START.outcomes)) * 42)
  const forecastValue = example ? (unlocked ? `${confPct}%` : "Calibrating") : stats.forecastValue
  const forecastNote = example
    ? unlocked
      ? `Scored against ${EXAMPLE_START.target} outcomes`
      : `${EXAMPLE_START.target - playback.exampleOutcomes} outcomes until scoring starts`
    : stats.forecastNote

  const events = example ? playback.exampleEvents : model.events
  const showLoading = !example && loading && !pageContext

  return (
    <section
      aria-labelledby="intelligence-core-heading"
      data-testid="intelligence-brain"
      data-example={example ? "true" : "false"}
      className={cn("flex flex-col gap-4", className)}
    >
      {/* Intelligence core control bar */}
      <div className={cn(panel, "flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5")}>
        <h2 id="intelligence-core-heading" className="flex items-center gap-2 text-[15px] font-semibold text-foreground">
          <span className="relative flex h-2 w-2" aria-hidden>
            {!paused && !quiet && !prefersReduced ? (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50" style={{ background: TONE_VAR[chip.tone] }} />
            ) : null}
            <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: TONE_VAR[chip.tone] }} />
          </span>
          Intelligence core
        </h2>
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{
            color: TONE_VAR[chip.tone],
            background: `color-mix(in srgb, ${TONE_VAR[chip.tone]} 14%, transparent)`,
          }}
        >
          {chip.label}
        </span>
        <span className="font-mono text-xs text-[color:var(--g-text-muted)]" aria-live="polite">
          {note}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Data shown" className={segment}>
            {(["example", "live"] as const).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={mode === m}
                onClick={() => switchMode(m)}
                className={cn(
                  segmentButton,
                  mode === m
                    ? "bg-[color:var(--g-surface-1)] text-foreground shadow-sm"
                    : "text-[color:var(--g-text-secondary)] hover:text-foreground",
                )}
              >
                {m === "example" ? "Example data" : "Live data"}
              </button>
            ))}
          </div>
          <div role="group" aria-label="Playback speed" className={segment}>
            {SPEEDS.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={speed === s}
                onClick={() => setSpeed(s)}
                className={cn(
                  segmentButton,
                  "px-2.5 font-mono text-xs",
                  speed === s
                    ? "bg-[color:var(--g-surface-1)] text-foreground shadow-sm"
                    : "text-[color:var(--g-text-secondary)] hover:text-foreground",
                )}
              >
                {s}×
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            aria-pressed={paused}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-[10px] bg-foreground px-3.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {paused ? <Play className="h-3.5 w-3.5" fill="currentColor" aria-hidden /> : <Pause className="h-3.5 w-3.5" fill="currentColor" aria-hidden />}
            {paused ? "Play" : "Pause"}
          </button>
        </div>
      </div>

      {/* Headline numbers */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Signals processed today"
          value={formatCount(example ? playback.exampleSignals : stats.signalsToday)}
          sub={stats.signalsSub}
        />
        <StatCard
          label="Connections strengthened"
          value={formatCount(example ? playback.exampleStrength : stats.connections)}
          sub={example ? "Links that got more certain this session" : stats.connectionsSub}
          valueClass="text-[color:var(--g-intelligence)]"
        />
        <StatCard
          label="Outcomes fed back"
          value={`${formatCount(fed)} / ${formatCount(target)}`}
          valueClass="text-[color:var(--g-approval)]"
        >
          <span
            className="mt-1 block h-1.5 overflow-hidden rounded-full bg-[color:var(--g-approval-soft)]"
            role="progressbar"
            aria-label="Outcomes until scoring starts"
            aria-valuemin={0}
            aria-valuemax={target ?? 0}
            aria-valuenow={fed ?? 0}
            title={example ? undefined : "Measured outcomes for your best-measured agent, against the number scoring needs"}
          >
            <span
              className="block h-full rounded-full bg-[color:var(--g-approval)] transition-[width] duration-500"
              style={{ width: `${target ? Math.min(100, Math.round(((fed ?? 0) / target) * 100)) : 0}%` }}
            />
          </span>
        </StatCard>
        <StatCard
          label="Forecast confidence"
          value={forecastValue}
          sub={forecastNote}
          valueClass={example || stats.forecastScored || forecastValue === "Calibrating" ? "text-[color:var(--g-brand-active,var(--g-brand))] dark:text-[color:var(--g-brand)]" : undefined}
        />
      </div>

      {/* Map + activity */}
      <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section
          ref={mapRef}
          aria-labelledby="overview-map-heading"
          className={cn(panel, "relative flex min-w-0 scroll-mt-24 flex-col gap-3 p-4 sm:p-5")}
          style={{
            backgroundImage: "radial-gradient(var(--g-border-subtle) 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="overview-map-heading" className="text-[17px] font-semibold text-foreground">
              How Gravitre is connecting the dots
            </h2>
            <span className="text-xs text-[color:var(--g-text-muted)]">Hover to follow a path. Click to drill in.</span>
          </div>
          <FlowMap
            model={model}
            placed={placed}
            playback={playback}
            highlightNodes={highlight?.nodes ?? null}
            highlightEdges={highlight?.edges ?? null}
            selectedNodeId={selectedNodeId}
            selectedLayer={selectedLayer}
            nodeSub={nodeSub}
            onHover={setHover}
            onSelectNode={selectNode}
            onSelectLayer={(id) => {
              setSelection({ kind: "layer", id })
              setTrace(null)
            }}
            notice={
              unlocked ? (
                <p role="status" className="flex items-center gap-2 text-[13px] text-[color:var(--g-brand-active,var(--g-brand))]">
                  <span className="h-2 w-2 rounded-full bg-[color:var(--g-brand)]" aria-hidden />
                  Forecasts unlocked. {EXAMPLE_START.target} outcomes captured, scoring has started.
                </p>
              ) : null
            }
            overlay={
              showLoading ? (
                <div className="absolute inset-0 grid place-items-center">
                  <span className={cn(panel, "px-4 py-2 text-[13px] text-[color:var(--g-text-secondary)]")}>Loading what Gravitre knows…</span>
                </div>
              ) : quiet ? (
                <div className="pointer-events-none absolute inset-0 grid place-items-center px-6 pb-16 pt-24">
                  <div className="pointer-events-auto flex max-w-[420px] flex-col items-center gap-3 rounded-2xl border border-[color:var(--g-approval)]/30 bg-[color:var(--g-surface-1)] px-6 py-5 text-center shadow-lg">
                    <span className="rounded-md bg-[color:var(--g-approval-soft)] px-2 py-0.5 font-mono text-[11px] text-[color:var(--g-approval)]">
                      {quiet.since}
                    </span>
                    <strong className="text-base font-semibold text-foreground">The core is quiet</strong>
                    <span className="text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">{quiet.body}</span>
                    <div className="flex flex-wrap justify-center gap-2">
                      {quiet.resyncIds.length ? (
                        <button
                          type="button"
                          onClick={() => void resync()}
                          disabled={resyncing}
                          className="min-h-9 rounded-[8px] bg-foreground px-3 text-[13px] font-medium text-background hover:opacity-90 disabled:opacity-50"
                        >
                          {resyncing ? "Resyncing…" : "Resync sources"}
                        </button>
                      ) : (
                        <Link
                          href={APP_ROUTES.connectors}
                          className="inline-flex min-h-9 items-center rounded-[8px] bg-foreground px-3 text-[13px] font-medium text-background hover:opacity-90"
                        >
                          Connect a source
                        </Link>
                      )}
                      <button
                        type="button"
                        onClick={() => switchMode("example")}
                        className="min-h-9 rounded-[8px] border border-[color:var(--g-border-default)] px-3 text-[13px] font-medium text-foreground hover:bg-[color:var(--g-surface-2)]"
                      >
                        Watch example data
                      </button>
                    </div>
                  </div>
                </div>
              ) : null
            }
          />
        </section>

        <aside aria-label="Inspector" className={cn(panel, "flex min-w-0 flex-col gap-3 p-4 sm:p-5")}>
          <FlowInspector
            model={model}
            placed={placed}
            selection={selection}
            events={events}
            streamTitle={quiet ? "Recent activity" : "Live activity"}
            streamMeta={
              quiet
                ? liveModel.lastSignalAt
                  ? `paused since ${shortDate(liveModel.lastSignalAt)}`
                  : "no signal yet"
                : `${inFlight} in flight`
            }
            live={!quiet && !paused}
            now={playback.now}
            traceId={trace?.id ?? null}
            onTrace={(e) => {
              setTrace((cur) => (cur?.id === e.id ? null : e))
              setSelection(null)
            }}
            onBack={() => {
              setSelection(null)
              setTrace(null)
            }}
            onSelectNode={selectNode}
            onSelectLayer={(id) => setSelection({ kind: "layer", id })}
            nodeSignals={nodeSignals}
            nodeStrength={nodeStrength}
          />
        </aside>
      </div>

      <LearningCards
        learnings={model.learnings}
        example={example}
        reinforced={playback.exampleReinforced}
        onTrace={traceLearning}
      />
    </section>
  )
}
