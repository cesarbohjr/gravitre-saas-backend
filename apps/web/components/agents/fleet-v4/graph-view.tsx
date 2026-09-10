"use client"

import { useMemo } from "react"
import { cn } from "@/lib/utils"
import { NucleoConnector, NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { layoutFleetGraph } from "@/lib/agents-fleet-graph"
import { GravitreAgentNode } from "./gravitre-agent-node"
import type { FleetAgent, FleetEdge, FleetGraphExtraNode } from "./types"

const NODE_W = 188
const NODE_H = 56

/**
 * Fleet GRAPH — structural + binding edges only (parent, swarm, connectors).
 * No invented collaborates/escalates. Activity pulse only on live swarm edges.
 */
export function GraphView({
  agents,
  edges,
  extraNodes = [],
  selectedId,
  onSelect,
  activeAgentIds,
  emptyHint,
  className,
}: {
  agents: FleetAgent[]
  edges: FleetEdge[]
  extraNodes?: FleetGraphExtraNode[]
  selectedId?: string | null
  onSelect?: (id: string) => void
  activeAgentIds?: Set<string>
  emptyHint?: string
  className?: string
}) {
  const positions = useMemo(
    () => layoutFleetGraph(agents, extraNodes),
    [agents, extraNodes],
  )

  const bounds = useMemo(() => {
    const pts = Object.values(positions)
    if (pts.length === 0) return { w: 640, h: 360 }
    const maxX = Math.max(...pts.map((p) => p.x)) + NODE_W + 48
    const maxY = Math.max(...pts.map((p) => p.y)) + NODE_H + 64
    return { w: Math.max(640, maxX), h: Math.max(360, maxY) }
  }, [positions])

  const edgePath = (from: string, to: string) => {
    const a = positions[from]
    const b = positions[to]
    if (!a || !b) return null
    const x1 = a.x + NODE_W
    const y1 = a.y + NODE_H / 2
    const x2 = b.x
    const y2 = b.y + NODE_H / 2
    const mx = (x1 + x2) / 2
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
  }

  if (agents.length === 0) {
    return (
      <div
        className={cn(
          "flex min-h-[280px] items-center justify-center rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)]/30 p-6 text-sm text-[color:var(--g-text-muted)]",
          className,
        )}
      >
        {emptyHint ?? "No agents to graph."}
      </div>
    )
  }

  const live = Boolean(activeAgentIds && activeAgentIds.size > 0)

  return (
    <div
      className={cn(
        "relative min-h-[420px] overflow-auto rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)]/30",
        className,
      )}
    >
      <div className="relative p-4" style={{ minWidth: bounds.w, minHeight: bounds.h }}>
        <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
          {edges.map((edge) => {
            const d = edgePath(edge.source, edge.target)
            if (!d) return null
            const active = Boolean(edge.active)
            const dashed =
              edge.kind === "uses_connector" || edge.kind === "collaborates_with"
            return (
              <g key={edge.id}>
                <path
                  d={d}
                  fill="none"
                  stroke={active ? "var(--g-brand)" : "var(--color-line, #d4d4d8)"}
                  strokeWidth={active ? 2 : 1.25}
                  strokeDasharray={dashed ? "5 4" : undefined}
                  opacity={active ? 1 : 0.75}
                />
                {active ? (
                  <circle r="3.5" fill="var(--g-brand)">
                    <animateMotion dur="1.6s" repeatCount="indefinite" path={d} />
                  </circle>
                ) : null}
              </g>
            )
          })}
        </svg>

        {agents.map((agent) => {
          const pos = positions[agent.id]
          if (!pos) return null
          const executing = activeAgentIds?.has(agent.id)
          return (
            <div key={agent.id} className="absolute" style={{ left: pos.x, top: pos.y }}>
              <GravitreAgentNode
                agent={agent}
                selected={selectedId === agent.id}
                executing={executing}
                onSelect={onSelect}
              />
            </div>
          )
        })}

        {extraNodes.map((node) => {
          const pos = positions[node.id]
          if (!pos) return null
          const Icon = node.kind === "workflow" ? NucleoWorkflow : NucleoConnector
          return (
            <div
              key={node.id}
              className="absolute flex w-[160px] items-center gap-2 rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-1)] px-3 py-2 shadow-[var(--np-shadow)]"
              style={{ left: pos.x, top: pos.y }}
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-md border border-cyan-200/80 bg-cyan-50/90 text-cyan-700 dark:border-cyan-800/45 dark:bg-cyan-950/25 dark:text-cyan-300">
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
                  {node.kind === "workflow" ? "Workflow" : "Connector"}
                </p>
                <p className="truncate text-sm font-medium">{node.label}</p>
              </div>
            </div>
          )
        })}

        <div className="absolute bottom-4 left-4 flex flex-wrap gap-3 text-[10px] text-[color:var(--g-text-muted)]">
          <span>── parent / swarm</span>
          <span>- - uses connector</span>
          {live ? <span className="text-[color:var(--g-brand)]">● live swarm path</span> : null}
          {edges.length === 0 ? (
            <span>No relationship edges yet — connectors appear when agents have connected systems</span>
          ) : null}
        </div>
      </div>
    </div>
  )
}
