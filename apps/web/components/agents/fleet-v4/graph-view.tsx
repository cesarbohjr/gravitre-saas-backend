"use client"

import { useCallback, useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { ConnectorsAtmosphere } from "@/components/gravitre/connectors-atmosphere"
import { NucleoConnector, NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { layoutFleetGraph } from "@/lib/agents-fleet-graph"
import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { DepartmentDropZone } from "./department-drop-zone"
import { FLEET_DEPARTMENT_ORDER } from "./fleet-department-dnd"
import { GravitreAgentNode } from "./gravitre-agent-node"
import type { AgentDepartmentId, FleetAgent, FleetEdge, FleetGraphExtraNode } from "./types"

const NODE_W = 188
const NODE_H = 56

function FleetEdgePath({
  edgeId,
  d,
  active,
  dashed,
  sweep,
}: {
  edgeId: string
  d: string
  active: boolean
  dashed: boolean
  sweep: boolean
}) {
  const reactId = useId()
  const gradientId = `fleet-edge-${edgeId}-${reactId.replace(/:/g, "")}`

  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke="var(--color-line, #eaedf1)"
        strokeWidth={active ? 2 : 1.5}
        strokeDasharray={dashed ? "5 4" : undefined}
        strokeLinecap="round"
      />
      {sweep ? (
        <>
          <path
            d={d}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={active ? 2.25 : 1.75}
            strokeLinecap="round"
          />
          <defs>
            <motion.linearGradient
              id={gradientId}
              gradientUnits="userSpaceOnUse"
              initial={{ x1: "0%", x2: "12%", y1: "0%", y2: "0%" }}
              animate={{ x1: "88%", x2: "100%", y1: "0%", y2: "0%" }}
              transition={{
                duration: active ? 1.6 : 2.4,
                repeat: Infinity,
                repeatType: "loop",
                ease: "easeInOut",
                repeatDelay: active ? 0.4 : 1,
              }}
            >
              <stop stopColor="var(--color-line, #EAEDF1)" />
              <stop
                offset="0.5"
                stopColor={active ? "var(--color-blue-500, #3b82f6)" : "var(--color-brand, #2563eb)"}
              />
              <stop offset="1" stopColor="var(--color-line, #EAEDF1)" />
            </motion.linearGradient>
          </defs>
        </>
      ) : null}
      {active ? (
        <circle r="3.5" fill="var(--g-brand)">
          <animateMotion dur="1.6s" repeatCount="indefinite" path={d} />
        </circle>
      ) : null}
    </g>
  )
}

/**
 * Fleet GRAPH — Nodus connectors canvas + combo/tech-stack edge sweeps.
 * Pointer-drag repositions nodes; HTML5 DnD onto department chips reassigns teams.
 */
export function GraphView({
  agents,
  edges,
  extraNodes = [],
  selectedId,
  onSelect,
  onDepartmentChange,
  showEmptyDepartments = true,
  activeAgentIds,
  emptyHint,
  className,
}: {
  agents: FleetAgent[]
  edges: FleetEdge[]
  extraNodes?: FleetGraphExtraNode[]
  selectedId?: string | null
  onSelect?: (id: string) => void
  onDepartmentChange?: (agentId: string, department: AgentDepartmentId) => void
  /** Empty department drop chips only when filters are clear. */
  showEmptyDepartments?: boolean
  activeAgentIds?: Set<string>
  emptyHint?: string
  className?: string
}) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const [positionOverrides, setPositionOverrides] = useState<Record<string, { x: number; y: number }>>({})
  const [hoverDepartment, setHoverDepartment] = useState<AgentDepartmentId | null>(null)
  const dragRef = useRef<{
    agentId: string
    pointerId: number
    originX: number
    originY: number
    startLeft: number
    startTop: number
    moved: boolean
  } | null>(null)

  const departmentAtPoint = (clientX: number, clientY: number): AgentDepartmentId | null => {
    if (typeof document === "undefined") return null
    const stack = document.elementsFromPoint(clientX, clientY)
    for (const el of stack) {
      const zone = (el as Element).closest?.("[data-department-drop]") as HTMLElement | null
      const department = zone?.getAttribute("data-department-drop") as AgentDepartmentId | null
      if (department) return department
    }
    return null
  }

  const layoutPositions = useMemo(
    () => layoutFleetGraph(agents, extraNodes),
    [agents, extraNodes],
  )

  const positions = useMemo(() => {
    const merged: Record<string, { x: number; y: number }> = { ...layoutPositions }
    for (const [id, pos] of Object.entries(positionOverrides)) {
      if (merged[id] || agents.some((a) => a.id === id)) {
        merged[id] = pos
      }
    }
    return merged
  }, [agents, layoutPositions, positionOverrides])

  const bounds = useMemo(() => {
    const pts = Object.values(positions)
    if (pts.length === 0) return { w: 640, h: 360 }
    const maxX = Math.max(...pts.map((p) => p.x)) + NODE_W + 48
    const maxY = Math.max(...pts.map((p) => p.y)) + NODE_H + 64
    return { w: Math.max(720, maxX), h: Math.max(420, maxY) }
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

  const deptsPresent = useMemo(() => {
    const set = new Set(agents.map((a) => a.department))
    return FLEET_DEPARTMENT_ORDER.filter(
      (d) => set.has(d) || (showEmptyDepartments && Boolean(onDepartmentChange)),
    )
  }, [agents, onDepartmentChange, showEmptyDepartments])

  const onNodePointerDown = useCallback(
    (agentId: string, event: ReactPointerEvent) => {
      if (event.button !== 0) return
      const pos = positions[agentId]
      if (!pos) return
      event.preventDefault()
      event.currentTarget.setPointerCapture(event.pointerId)
      dragRef.current = {
        agentId,
        pointerId: event.pointerId,
        originX: event.clientX,
        originY: event.clientY,
        startLeft: pos.x,
        startTop: pos.y,
        moved: false,
      }
    },
    [positions],
  )

  const onNodePointerMove = useCallback((event: ReactPointerEvent) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    const dx = event.clientX - drag.originX
    const dy = event.clientY - drag.originY
    if (!drag.moved && Math.hypot(dx, dy) < 4) return
    drag.moved = true
    const next = {
      x: Math.max(0, drag.startLeft + dx),
      y: Math.max(0, drag.startTop + dy),
    }
    setPositionOverrides((prev) => ({ ...prev, [drag.agentId]: next }))
    setHoverDepartment(departmentAtPoint(event.clientX, event.clientY))
  }, [])

  const onNodePointerUp = useCallback(
    (event: ReactPointerEvent) => {
      const drag = dragRef.current
      if (!drag || drag.pointerId !== event.pointerId) return
      try {
        event.currentTarget.releasePointerCapture(event.pointerId)
      } catch {
        /* already released */
      }
      const wasClick = !drag.moved
      const agentId = drag.agentId
      dragRef.current = null
      setHoverDepartment(null)

      if (wasClick) {
        onSelect?.(agentId)
        return
      }

      const department = departmentAtPoint(event.clientX, event.clientY)
      if (department && onDepartmentChange) {
        onDepartmentChange(agentId, department)
      }
    },
    [onDepartmentChange, onSelect],
  )

  if (agents.length === 0) {
    return (
      <div
        className={cn(
          "relative flex min-h-[280px] items-center justify-center overflow-hidden rounded-[var(--np-radius-lg)] border border-divide",
          className,
        )}
      >
        <ConnectorsAtmosphere className="z-0" />
        <p className="relative z-10 text-sm text-[color:var(--g-text-muted)]">
          {emptyHint ?? "No agents to graph."}
        </p>
      </div>
    )
  }

  const live = Boolean(activeAgentIds && activeAgentIds.size > 0)
  const canAssign = Boolean(onDepartmentChange)

  return (
    <div className={cn("space-y-3", className)}>
      {canAssign ? (
        <div className="relative z-10 flex flex-wrap gap-2">
          {deptsPresent.map((department) => {
            const count = agents.filter((a) => a.department === department).length
            return (
              <DepartmentDropZone
                key={department}
                department={department}
                onDropAgent={onDepartmentChange}
                className={cn(
                  "min-h-[3.25rem] min-w-[7.5rem] border border-divide bg-white px-2.5 py-2 shadow-[var(--np-shadow)]",
                  hoverDepartment === department &&
                    "border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]/50 ring-2 ring-[color:var(--g-brand)]/35",
                )}
                highlightClassName="border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]/50 ring-2 ring-[color:var(--g-brand)]/35"
              >
                <p
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-wide",
                    DEPARTMENT_ACCENT[department].accentClass,
                  )}
                >
                  {DEPARTMENT_ACCENT[department].label}
                </p>
                <p className="text-[10px] tabular-nums text-[color:var(--g-text-muted)]">
                  {count} · drop to assign
                </p>
              </DepartmentDropZone>
            )
          })}
        </div>
      ) : null}

      <div className="relative min-h-[420px] overflow-auto rounded-[var(--np-radius-lg)] border border-divide">
        <ConnectorsAtmosphere className="z-0" />
        <div
          ref={canvasRef}
          className="relative z-10 p-4"
          style={{ minWidth: bounds.w, minHeight: bounds.h }}
        >
          <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
            {edges.map((edge) => {
              const d = edgePath(edge.source, edge.target)
              if (!d) return null
              const active = Boolean(edge.active)
              const dashed =
                edge.kind === "uses_connector" || edge.kind === "collaborates_with"
              return (
                <FleetEdgePath
                  key={edge.id}
                  edgeId={edge.id}
                  d={d}
                  active={active}
                  dashed={dashed}
                  sweep
                />
              )
            })}
          </svg>

          {agents.map((agent) => {
            const pos = positions[agent.id]
            if (!pos) return null
            const executing = activeAgentIds?.has(agent.id)
            return (
              <div
                key={agent.id}
                className="absolute touch-none cursor-grab active:cursor-grabbing"
                style={{ left: pos.x, top: pos.y }}
                onPointerDown={(event) => onNodePointerDown(agent.id, event)}
                onPointerMove={onNodePointerMove}
                onPointerUp={onNodePointerUp}
                onPointerCancel={onNodePointerUp}
              >
                <GravitreAgentNode
                  agent={agent}
                  selected={selectedId === agent.id}
                  executing={executing}
                  draggable={false}
                  // Selection handled on pointer-up when the gesture was a click.
                  onSelect={undefined}
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
                className="absolute flex w-[160px] items-center gap-2 rounded-[var(--np-radius-md)] border border-divide bg-white px-3 py-2 shadow-[var(--np-shadow)]"
                style={{ left: pos.x, top: pos.y }}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-md border border-cyan-300 bg-cyan-100 text-cyan-700 dark:border-cyan-700 dark:bg-cyan-950/50 dark:text-cyan-200">
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
            <span>Drag nodes to rearrange · release on a department chip to reassign</span>
            <span>── parent / swarm</span>
            <span>- - uses connector</span>
            {live ? <span className="text-[color:var(--g-brand)]">● live swarm path</span> : null}
            {edges.length === 0 ? (
              <span>
                No relationship edges yet — connectors appear when agents have connected systems
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
