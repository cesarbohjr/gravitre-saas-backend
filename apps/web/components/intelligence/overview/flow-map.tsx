"use client"

import type { KeyboardEvent, ReactNode } from "react"
import {
  MAP_HEIGHT,
  MAP_WIDTH,
  edgeKey,
  nodeY,
  type FlowLayerId,
  type FlowModel,
  type FlowNode,
  type FlowTone,
} from "@/components/intelligence/overview/flow-model"
import type { FlowPlayback } from "@/components/intelligence/overview/use-flow-playback"
import { cn } from "@/lib/utils"

export const TONE_VAR: Record<FlowTone, string> = {
  neutral: "var(--g-text-muted)",
  intelligence: "var(--g-intelligence)",
  approval: "var(--g-approval)",
  primary: "var(--g-text-primary)",
  brand: "var(--g-brand)",
  danger: "var(--g-danger)",
}

export type PlacedNode = FlowNode & { x: number; y: number; tone: FlowTone }

export function placeNodes(model: FlowModel): Map<string, PlacedNode> {
  const out = new Map<string, PlacedNode>()
  for (const layer of model.layers) {
    const list = model.nodes.filter((n) => n.layer === layer.id)
    list.forEach((n, i) => out.set(n.id, { ...n, x: layer.x, y: nodeY(i, list.length), tone: layer.tone }))
  }
  return out
}

type Point = { x: number; y: number }

function bez(a: Point, b: Point, t: number): Point {
  const dir = b.x > a.x ? 1 : -1
  const x1 = a.x + 11 * dir
  const x2 = b.x - 11 * dir
  const cx = (x1 + x2) / 2
  const m = 1 - t
  return {
    x: m * m * m * x1 + 3 * m * m * t * cx + 3 * m * t * t * cx + t * t * t * x2,
    y: m * m * m * a.y + 3 * m * m * t * a.y + 3 * m * t * t * b.y + t * t * t * b.y,
  }
}

function edgePath(a: Point, b: Point): string {
  const x1 = a.x + 11
  const x2 = b.x - 11
  const cx = (x1 + x2) / 2
  return `M${x1} ${a.y} C${cx} ${a.y} ${cx} ${b.y} ${x2} ${b.y}`
}

function shortLabel(label: string, max = 22): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label
}

export function FlowMap({
  model,
  placed,
  playback,
  highlightNodes,
  highlightEdges,
  selectedNodeId,
  selectedLayer,
  nodeSub,
  onHover,
  onSelectNode,
  onSelectLayer,
  overlay,
  notice,
}: {
  model: FlowModel
  placed: Map<string, PlacedNode>
  playback: FlowPlayback
  highlightNodes: Set<string> | null
  highlightEdges: Set<string> | null
  selectedNodeId: string | null
  selectedLayer: FlowLayerId | null
  nodeSub: (node: PlacedNode) => string
  onHover: (id: string | null) => void
  onSelectNode: (id: string) => void
  onSelectLayer: (id: FlowLayerId) => void
  overlay?: ReactNode
  notice?: ReactNode
}) {
  // Journeys mutate between frames, so this is recomputed on every render.
  const activeEdges = new Map<string, "forward" | "feedback">()
  for (const j of playback.journeys) {
    if (j.i >= j.path.length - 1) continue
    const a = j.path[j.i]
    const b = j.path[j.i + 1]
    activeEdges.set(edgeKey(a, b), j.feedback ? "feedback" : "forward")
    activeEdges.set(edgeKey(b, a), j.feedback ? "feedback" : "forward")
  }

  const edges = model.edges
    .map((e) => {
      const a = placed.get(e.a)
      const b = placed.get(e.b)
      if (!a || !b) return null
      const weight = e.weight + (e.evidence ? (playback.boost[e.key] ?? 0) : 0)
      let color = "var(--g-border-default)"
      let opacity = e.evidence ? 0.9 : 0.55
      if (highlightEdges) {
        if (highlightEdges.has(e.key)) {
          color = "var(--g-text-primary)"
          opacity = 0.55
        } else {
          opacity = 0.08
        }
      }
      const active = activeEdges.get(e.key)
      if (active && (!highlightEdges || highlightEdges.has(e.key))) {
        color = active === "feedback" ? "var(--g-approval)" : "var(--g-brand)"
        opacity = 0.9
      }
      return { key: e.key, d: edgePath(a, b), color, opacity, width: 0.5 + weight * 0.42 }
    })
    .filter((e): e is NonNullable<typeof e> => e != null)

  const dots: Array<{ key: string; x: number; y: number; r: number; color: string; opacity: number }> = []
  for (const j of playback.journeys) {
    if (j.i >= j.path.length - 1) continue
    const a = placed.get(j.path[j.i])
    const b = placed.get(j.path[j.i + 1])
    if (!a || !b) continue
    if (highlightEdges && !highlightEdges.has(edgeKey(a.id, b.id)) && !highlightEdges.has(edgeKey(b.id, a.id))) continue
    const color = j.feedback ? "var(--g-approval)" : "var(--g-brand)"
    ;[
      [0, 4.5, 1],
      [0.05, 3.4, 0.5],
      [0.1, 2.4, 0.25],
      [0.15, 1.6, 0.12],
    ].forEach(([lag, r, o], i) => {
      const p = bez(a, b, Math.max(0, j.t - lag))
      dots.push({ key: `${j.id}:${i}`, x: p.x, y: p.y, r, color, opacity: o })
    })
  }

  const onNodeKey = (event: KeyboardEvent<SVGGElement>, id: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      onSelectNode(id)
    }
  }

  return (
    <div className="relative flex flex-col gap-3">
      <div role="group" aria-label="Layers" className="grid grid-cols-5 gap-1.5">
        {model.layers.map((layer) => {
          const on =
            selectedLayer === layer.id || (selectedNodeId != null && placed.get(selectedNodeId)?.layer === layer.id)
          return (
            <button
              key={layer.id}
              type="button"
              aria-pressed={on}
              onClick={() => onSelectLayer(layer.id)}
              className={cn(
                "flex min-h-11 min-w-0 flex-col items-center justify-center gap-0.5 rounded-[var(--np-radius-sm,6px)] border px-1 py-1.5 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                on
                  ? "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-2)]"
                  : "border-transparent hover:bg-[color:var(--g-surface-2)]/60",
              )}
            >
              <span className="flex max-w-full items-center gap-1.5 truncate text-xs font-semibold text-foreground sm:text-[13px]">
                <span className="h-2 w-2 shrink-0 rounded-[2px]" style={{ background: TONE_VAR[layer.tone] }} aria-hidden />
                {layer.name}
              </span>
              <span className="hidden max-w-full truncate font-mono text-[10.5px] text-[color:var(--g-text-muted)] sm:block">
                {layer.count}
              </span>
            </button>
          )
        })}
      </div>

      <div className="relative -mx-1 overflow-x-auto px-1">
        <svg
          viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
          className="block h-auto w-full min-w-[640px] overflow-visible"
          role="img"
          aria-label="Map of how sources feed knowledge, learnings, models and forecasts"
        >
          {edges.map((e) => (
            <path
              key={e.key}
              d={e.d}
              fill="none"
              strokeLinecap="round"
              style={{ stroke: e.color, opacity: e.opacity, strokeWidth: e.width }}
            />
          ))}
          {dots.map((d) => (
            <circle key={d.key} cx={d.x} cy={d.y} r={d.r} style={{ fill: d.color, opacity: d.opacity }} />
          ))}
          {[...placed.values()].map((n) => {
            const act = playback.act[n.id] ?? 0
            const dim = highlightNodes ? (highlightNodes.has(n.id) ? 1 : 0.18) : 1
            const dashed = n.placeholder || n.scored === false
            const color = TONE_VAR[n.tone]
            const sub = nodeSub(n)
            return (
              <g
                key={n.id}
                transform={`translate(${n.x} ${n.y})`}
                style={{ opacity: dim, cursor: "pointer" }}
                role="button"
                tabIndex={0}
                aria-label={`${n.label}${sub ? `, ${sub}` : ""}. Open details`}
                aria-pressed={selectedNodeId === n.id}
                onMouseEnter={() => onHover(n.id)}
                onMouseLeave={() => onHover(null)}
                onFocus={() => onHover(n.id)}
                onBlur={() => onHover(null)}
                onClick={() => onSelectNode(n.id)}
                onKeyDown={(event) => onNodeKey(event, n.id)}
                className="outline-none [&:focus-visible>circle.ring]:opacity-100"
              >
                <circle r={10 + act * 16} style={{ fill: color, opacity: 0.06 + act * 0.22 }} />
                <circle r={17} fill="transparent" />
                <circle
                  className="ring"
                  r={15}
                  fill="none"
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                  style={{ stroke: "var(--g-text-primary)", opacity: selectedNodeId === n.id ? 1 : 0 }}
                />
                <circle
                  r={9}
                  strokeWidth={2}
                  strokeDasharray={dashed ? "3 3" : undefined}
                  style={{ fill: "var(--g-surface-1)", stroke: color }}
                />
                {n.placeholder ? null : <circle r={3.5 + act * 2} style={{ fill: color }} />}
                <text
                  y={28}
                  textAnchor="middle"
                  fontSize={13}
                  fontWeight={500}
                  className="font-sans"
                  style={{ fill: n.placeholder ? "var(--g-text-muted)" : "var(--g-text-primary)" }}
                >
                  {shortLabel(n.label)}
                </text>
                {sub ? (
                  <text y={43} textAnchor="middle" fontSize={10.5} className="font-mono" style={{ fill: "var(--g-text-muted)" }}>
                    {shortLabel(sub, 26)}
                  </text>
                ) : null}
              </g>
            )
          })}
        </svg>
        {overlay}
      </div>

      {notice}

      <ul
        aria-label="Legend"
        className="flex flex-wrap gap-x-5 gap-y-1.5 border-t border-[color:var(--g-border-subtle)] pt-3 text-xs text-[color:var(--g-text-secondary)]"
      >
        <li className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[color:var(--g-brand)]" aria-hidden />
          Signal moving forward
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[color:var(--g-approval)]" aria-hidden />
          Outcome flowing back
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-[3px] w-4 rounded-full bg-[color:var(--g-text-muted)]" aria-hidden />
          Thicker line, stronger connection
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-dashed border-[color:var(--g-brand)]" aria-hidden />
          Not scored yet
        </li>
      </ul>
    </div>
  )
}
